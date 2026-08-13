"""Re-grounded human review and fail-closed acceptance for Agile candidates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from src.agile import (
    AgileArtifact,
    AgileArtifactBatch,
    AgileBehaviorProfile,
    AgileContractError,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
    validate_artifact_hierarchy,
)
from src.agile_generation import (
    AgileGenerationRequest,
    AgileGenerationResult,
    AgileGenerationState,
    MissingRequirement,
    NonSaveableProposal,
)
from src.agile_profiles import default_profile_selection
from src.agile_prompt_catalog import AgilePromptError, AgilePromptSource, get_agile_prompt
from src.claim_support import (
    AssessableClaim,
    ClaimSupportAssessment,
    assess_all_claims,
    extract_assessable_claims,
)
from src.database import (
    DATABASE_FILE,
    save_reviewed_agile_batch,
)
from src.semantic_retrieval import RetrievalChunk


class AgileReviewAction(str, Enum):
    BEGIN = "begin"
    REVISE = "revise"
    REJECT = "reject"
    ACCEPT = "accept"


class AgileReviewBlockCode(str, Enum):
    INVALID_REVIEW = "invalid_review"
    INVALID_TRANSITION = "invalid_transition"
    STALE_VERSION = "stale_version"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_METADATA = "invalid_metadata"
    INELIGIBLE_SOURCE = "ineligible_source"
    STALE_SOURCE = "stale_source"
    INVALID_CITATION = "invalid_citation"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    MISSING_REQUIREMENT = "missing_requirement"
    NON_SAVEABLE_PROPOSAL = "non_saveable_proposal"
    STALE_ASSESSMENT = "stale_assessment"
    MISSING_REVIEWER = "missing_reviewer"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass(frozen=True)
class AgileReviewBlockingReason:
    code: AgileReviewBlockCode
    message: str
    artifact_id: str | None = None
    claim_id: str | None = None


class AgileReviewError(ValueError):
    """A review action failed closed with UI-ready structured reasons."""

    def __init__(self, reasons: tuple[AgileReviewBlockingReason, ...]):
        self.reasons = reasons
        super().__init__("; ".join(reason.message for reason in reasons))


@dataclass(frozen=True)
class AgileAcceptanceGate:
    gate_id: str
    passed: bool
    reasons: tuple[AgileReviewBlockingReason, ...] = ()


@dataclass(frozen=True)
class AgileReviewEvent:
    event_id: str
    action: AgileReviewAction
    revision: int
    from_state: AgileReviewState
    to_state: AgileReviewState
    reviewer_id: str
    occurred_at: str
    reason: str | None = None


@dataclass(frozen=True)
class AgileReviewBatch:
    """Immutable in-memory evidence for one generated batch and review cycle."""

    review_id: str
    request: AgileGenerationRequest
    original_generation: AgileGenerationResult
    original_artifacts: tuple[AgileArtifact, ...]
    artifacts: tuple[AgileArtifact, ...]
    source_chunks: tuple[RetrievalChunk, ...]
    prompt_sources: tuple[AgilePromptSource, ...]
    claims: tuple[AssessableClaim, ...]
    assessments: tuple[ClaimSupportAssessment, ...]
    missing_requirements: tuple[MissingRequirement, ...]
    proposals: tuple[NonSaveableProposal, ...]
    gates: tuple[AgileAcceptanceGate, ...]
    events: tuple[AgileReviewEvent, ...]
    review_state: AgileReviewState
    revision: int
    assessed_revision: int
    created_at: str
    updated_at: str
    accepted_batch: AgileArtifactBatch | None = None

    @property
    def can_accept(self) -> bool:
        return (
            self.review_state is AgileReviewState.PENDING_REVIEW
            and self.assessed_revision == self.revision
            and bool(self.gates)
            and all(gate.passed for gate in self.gates)
        )


@dataclass(frozen=True)
class AgileAcceptanceResult:
    review: AgileReviewBatch
    batch: AgileArtifactBatch
    created: bool


class ReviewSourceProvider(Protocol):
    def revalidate(self, chunks: tuple[RetrievalChunk, ...]) -> bool: ...


ReviewedBatchSaver = Callable[
    [AgileArtifactBatch, tuple[RetrievalChunk, ...]],
    tuple[AgileArtifactBatch, bool],
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _review_id() -> str:
    return f"agile-review-{uuid4().hex}"


def _text(value: object, field_name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise AgileReviewError(
            (
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.INVALID_REVIEW,
                    f"{field_name} is required and must be at most {maximum:,} characters.",
                ),
            )
        )
    return value.strip()


def _domain_source(source: AgilePromptSource) -> AgileSourceReference:
    return AgileSourceReference(
        reference_id=source.reference_id,
        product_id=source.product_id,
        product_name=source.product_name,
        document_id=source.document_id,
        document_title=source.document_title,
        document_type=source.document_type,
        section_key=source.section_key,
        section_title=source.section_title,
    )


def _claim_map(
    artifacts: tuple[AgileArtifact, ...],
) -> dict[tuple[str, str], tuple[str, ...]]:
    mapping: dict[tuple[str, str], tuple[str, ...]] = {}
    for artifact in artifacts:
        artifact_refs = tuple(
            sorted(source.reference_id for source in artifact.source_references)
        )
        mapping[(artifact.artifact_id, "title")] = artifact_refs
        mapping[(artifact.artifact_id, "description")] = artifact_refs
        if artifact.parent_artifact_id is not None:
            mapping[(artifact.artifact_id, "parent_relationship")] = artifact_refs
        for criterion in artifact.acceptance_criteria:
            mapping[
                (
                    artifact.artifact_id,
                    f"acceptance_criteria.{criterion.criterion_id}",
                )
            ] = tuple(
                sorted(source.reference_id for source in criterion.source_references)
            )
    return mapping


def _gate(
    gate_id: str, reasons: list[AgileReviewBlockingReason]
) -> AgileAcceptanceGate:
    return AgileAcceptanceGate(gate_id, not reasons, tuple(reasons))


class AgileReviewService:
    """Review, reassess, reject, and explicitly accept without a provider call."""

    def __init__(
        self,
        source_provider: ReviewSourceProvider,
        database_path: str | Path = DATABASE_FILE,
        *,
        timestamp_factory: Callable[[], str] = _utc_now,
        review_id_factory: Callable[[], str] = _review_id,
        saver: ReviewedBatchSaver | None = None,
    ) -> None:
        self._sources = source_provider
        self._timestamp = timestamp_factory
        self._review_id = review_id_factory
        self._saver = saver or (
            lambda batch, chunks: save_reviewed_agile_batch(
                batch, chunks, database_path
            )
        )

    def _evaluate(
        self,
        request: AgileGenerationRequest,
        artifacts: tuple[AgileArtifact, ...],
        chunks: tuple[RetrievalChunk, ...],
        sources: tuple[AgilePromptSource, ...],
        missing: tuple[MissingRequirement, ...],
        proposals: tuple[NonSaveableProposal, ...],
        expected_profile: AgileBehaviorProfile,
    ) -> tuple[
        tuple[AssessableClaim, ...],
        tuple[ClaimSupportAssessment, ...],
        tuple[AgileAcceptanceGate, ...],
    ]:
        structure: list[AgileReviewBlockingReason] = []
        metadata: list[AgileReviewBlockingReason] = []
        source_scope: list[AgileReviewBlockingReason] = []
        citations: list[AgileReviewBlockingReason] = []
        support: list[AgileReviewBlockingReason] = []
        gaps: list[AgileReviewBlockingReason] = []
        proposal_reasons: list[AgileReviewBlockingReason] = []

        try:
            validate_artifact_hierarchy(artifacts, product_id=request.product_id)
        except AgileContractError as error:
            structure.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.INVALID_STRUCTURE, str(error)
                )
            )
        try:
            get_agile_prompt(
                request.prompt_id,
                request.prompt_version,
                request.task,
                request.artifact_type,
            )
            if default_profile_selection(request.profile) is not expected_profile:
                raise AgilePromptError(
                    "The review profile no longer matches the generated content."
                )
        except AgilePromptError as error:
            metadata.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.INVALID_METADATA, str(error)
                )
            )

        source_by_id = {source.reference_id: source for source in sources}
        if (
            not chunks
            or len(source_by_id) != len(sources)
            or {chunk.chunk_id for chunk in chunks} != set(source_by_id)
        ):
            source_scope.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.INELIGIBLE_SOURCE,
                    "Review sources are missing, duplicated, or inconsistent.",
                )
            )
        selected_documents = set(request.selected_document_ids)
        if any(
            source.product_id != request.product_id
            or source.document_id not in selected_documents
            for source in sources
        ):
            source_scope.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.INELIGIBLE_SOURCE,
                    "Every source must remain within the selected product and document scope.",
                )
            )
        try:
            sources_are_current = self._sources.revalidate(chunks)
        except Exception:
            sources_are_current = False
        if not sources_are_current:
            source_scope.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.STALE_SOURCE,
                    "A selected source changed or became ineligible after generation.",
                )
            )

        allowed = {key: _domain_source(value) for key, value in source_by_id.items()}
        for artifact in artifacts:
            owned_sources = (
                *artifact.source_references,
                *(
                    source
                    for criterion in artifact.acceptance_criteria
                    for source in criterion.source_references
                ),
            )
            for source in owned_sources:
                if allowed.get(source.reference_id) != source:
                    citations.append(
                        AgileReviewBlockingReason(
                            AgileReviewBlockCode.INVALID_CITATION,
                            "A citation is unresolved, fabricated, stale, or outside the reviewed context.",
                            artifact_id=artifact.artifact_id,
                        )
                    )

        claims = extract_assessable_claims(artifacts, _claim_map(artifacts))
        assessments = assess_all_claims(claims, sources)
        for assessment in assessments:
            if not assessment.supported:
                support.append(
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.UNSUPPORTED_CLAIM,
                        (
                            f"Claim {assessment.claim.claim_id} is "
                            f"{assessment.outcome.value}: {assessment.reason.value}."
                        ),
                        artifact_id=assessment.claim.artifact_id,
                        claim_id=assessment.claim.claim_id,
                    )
                )
        for requirement in missing:
            gaps.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.MISSING_REQUIREMENT,
                    f"Missing requirement {requirement.requirement_id} remains unresolved.",
                )
            )
        for proposal in proposals:
            proposal_reasons.append(
                AgileReviewBlockingReason(
                    AgileReviewBlockCode.NON_SAVEABLE_PROPOSAL,
                    f"Proposal {proposal.proposal_id} is labeled non-saveable.",
                )
            )
        gates = (
            _gate("structured_contract_and_hierarchy", structure),
            _gate("profile_and_prompt_metadata", metadata),
            _gate("current_approved_source_scope", source_scope),
            _gate("citation_resolution", citations),
            _gate("claim_and_criterion_support", support),
            _gate("missing_requirements", gaps),
            _gate("non_saveable_proposals", proposal_reasons),
        )
        return claims, assessments, gates

    def begin_review(
        self,
        request: AgileGenerationRequest,
        generation: AgileGenerationResult,
        *,
        reviewer_id: str,
    ) -> AgileReviewBatch:
        reviewer = _text(reviewer_id, "Reviewer identity", 128)
        if not isinstance(request, AgileGenerationRequest) or not isinstance(
            generation, AgileGenerationResult
        ):
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_REVIEW,
                        "A validated generation request and result are required.",
                    ),
                )
            )
        if (
            generation.state
            not in {AgileGenerationState.GENERATED, AgileGenerationState.SUPPORT_BLOCKED}
            or not generation.requires_human_review
            or generation.explicitly_accepted
            or not generation.review_artifacts
            or generation.profile is not default_profile_selection(request.profile)
            or generation.prompt_id != request.prompt_id
            or generation.prompt_version != request.prompt_version
        ):
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_REVIEW,
                        "Only matching, unaccepted Agile generation output can enter review.",
                    ),
                )
            )
        review_id = _text(self._review_id(), "Review identifier", 128)
        now = self._timestamp()
        artifacts = tuple(generation.review_artifacts)
        claims, assessments, gates = self._evaluate(
            request,
            artifacts,
            generation.retrieval_chunks,
            generation.prompt_sources,
            generation.missing_requirements,
            generation.proposals,
            generation.profile,
        )
        event = AgileReviewEvent(
            f"{review_id}:1:begin",
            AgileReviewAction.BEGIN,
            1,
            AgileReviewState.PENDING_REVIEW,
            AgileReviewState.PENDING_REVIEW,
            reviewer,
            now,
        )
        return AgileReviewBatch(
            review_id=review_id,
            request=request,
            original_generation=generation,
            original_artifacts=artifacts,
            artifacts=artifacts,
            source_chunks=tuple(generation.retrieval_chunks),
            prompt_sources=tuple(generation.prompt_sources),
            claims=claims,
            assessments=assessments,
            missing_requirements=tuple(generation.missing_requirements),
            proposals=tuple(generation.proposals),
            gates=gates,
            events=(event,),
            review_state=AgileReviewState.PENDING_REVIEW,
            revision=1,
            assessed_revision=1,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _require_current_pending(
        review: AgileReviewBatch, expected_revision: int
    ) -> None:
        if not isinstance(review, AgileReviewBatch):
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_REVIEW,
                        "A validated Agile review is required.",
                    ),
                )
            )
        if expected_revision != review.revision:
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.STALE_VERSION,
                        "The requested review revision is stale.",
                    ),
                )
            )
        if review.review_state is not AgileReviewState.PENDING_REVIEW:
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_TRANSITION,
                        "Only a pending review can be revised, rejected, or newly accepted.",
                    ),
                )
            )

    def revise(
        self,
        review: AgileReviewBatch,
        artifacts: tuple[AgileArtifact, ...],
        *,
        expected_revision: int,
        reviewer_id: str,
    ) -> AgileReviewBatch:
        self._require_current_pending(review, expected_revision)
        reviewer = _text(reviewer_id, "Reviewer identity", 128)
        revised = tuple(artifacts)
        if not revised or any(not isinstance(item, AgileArtifact) for item in revised):
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_STRUCTURE,
                        "A revision must contain validated Agile artifacts.",
                    ),
                )
            )
        old_identity = tuple(
            (
                item.artifact_id,
                item.artifact_type,
                item.product_id,
                item.position,
                tuple((criterion.criterion_id, criterion.position) for criterion in item.acceptance_criteria),
            )
            for item in review.artifacts
        )
        new_identity = tuple(
            (
                item.artifact_id,
                item.artifact_type,
                item.product_id,
                item.position,
                tuple((criterion.criterion_id, criterion.position) for criterion in item.acceptance_criteria),
            )
            for item in revised
        )
        if new_identity != old_identity:
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.INVALID_STRUCTURE,
                        "Artifact and criterion identities and ordering are immutable during review.",
                    ),
                )
            )
        if revised == review.artifacts:
            return review
        revision = review.revision + 1
        now = self._timestamp()
        normalized = tuple(
            replace(
                artifact,
                review_state=AgileReviewState.PENDING_REVIEW,
                provenance=ContentProvenance.PRODUCT_MANAGER_EDITED,
                revision=revision,
                created_at=original.created_at,
                updated_at=now,
            )
            for artifact, original in zip(revised, review.original_artifacts, strict=True)
        )
        claims, assessments, gates = self._evaluate(
            review.request,
            normalized,
            review.source_chunks,
            review.prompt_sources,
            review.missing_requirements,
            review.proposals,
            review.original_generation.profile,
        )
        event = AgileReviewEvent(
            f"{review.review_id}:{revision}:revise",
            AgileReviewAction.REVISE,
            revision,
            AgileReviewState.PENDING_REVIEW,
            AgileReviewState.PENDING_REVIEW,
            reviewer,
            now,
        )
        return replace(
            review,
            artifacts=normalized,
            claims=claims,
            assessments=assessments,
            gates=gates,
            events=review.events + (event,),
            revision=revision,
            assessed_revision=revision,
            updated_at=now,
        )

    def reject(
        self,
        review: AgileReviewBatch,
        *,
        expected_revision: int,
        reviewer_id: str,
        reason: str,
    ) -> AgileReviewBatch:
        self._require_current_pending(review, expected_revision)
        reviewer = _text(reviewer_id, "Reviewer identity", 128)
        rejection = _text(reason, "Rejection reason", 2_000)
        now = self._timestamp()
        event = AgileReviewEvent(
            f"{review.review_id}:{review.revision}:reject",
            AgileReviewAction.REJECT,
            review.revision,
            AgileReviewState.PENDING_REVIEW,
            AgileReviewState.REJECTED,
            reviewer,
            now,
            rejection,
        )
        return replace(
            review,
            review_state=AgileReviewState.REJECTED,
            events=review.events + (event,),
            updated_at=now,
        )

    def accept(
        self,
        review: AgileReviewBatch,
        *,
        expected_revision: int,
        reviewer_id: str,
    ) -> AgileAcceptanceResult:
        if (
            isinstance(review, AgileReviewBatch)
            and review.review_state is AgileReviewState.ACCEPTED
            and review.accepted_batch is not None
            and expected_revision == review.revision
        ):
            saved, created = self._saver(review.accepted_batch, review.source_chunks)
            return AgileAcceptanceResult(review, saved, created)
        self._require_current_pending(review, expected_revision)
        reviewer = _text(reviewer_id, "Reviewer identity", 128)
        if review.assessed_revision != review.revision:
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.STALE_ASSESSMENT,
                        "The current revision has not been reassessed.",
                    ),
                )
            )
        claims, assessments, gates = self._evaluate(
            review.request,
            review.artifacts,
            review.source_chunks,
            review.prompt_sources,
            review.missing_requirements,
            review.proposals,
            review.original_generation.profile,
        )
        blocking = tuple(reason for gate in gates for reason in gate.reasons)
        if blocking:
            raise AgileReviewError(blocking)
        now = self._timestamp()
        accepted_artifacts = tuple(
            replace(
                artifact,
                review_state=AgileReviewState.ACCEPTED,
                revision=review.revision,
                updated_at=now,
            )
            for artifact in review.artifacts
        )
        try:
            accepted = AgileArtifactBatch(
                batch_id=review.review_id,
                product_id=review.request.product_id,
                behavior_profile=review.original_generation.profile,
                review_state=AgileReviewState.ACCEPTED,
                prompt_version=review.request.prompt_version,
                artifacts=accepted_artifacts,
                revision=review.revision,
                created_at=review.created_at,
                updated_at=now,
                accepted_at=now,
            )
            saved, created = self._saver(accepted, review.source_chunks)
        except Exception as error:
            raise AgileReviewError(
                (
                    AgileReviewBlockingReason(
                        AgileReviewBlockCode.PERSISTENCE_FAILED,
                        "The reviewed Agile batch failed final persistence validation; nothing was saved.",
                    ),
                )
            ) from error
        event = AgileReviewEvent(
            f"{review.review_id}:{review.revision}:accept",
            AgileReviewAction.ACCEPT,
            review.revision,
            AgileReviewState.PENDING_REVIEW,
            AgileReviewState.ACCEPTED,
            reviewer,
            now,
        )
        accepted_review = replace(
            review,
            artifacts=accepted_artifacts,
            claims=claims,
            assessments=assessments,
            gates=gates,
            events=review.events + (event,),
            review_state=AgileReviewState.ACCEPTED,
            assessed_revision=review.revision,
            updated_at=now,
            accepted_batch=saved,
        )
        return AgileAcceptanceResult(accepted_review, saved, created)
