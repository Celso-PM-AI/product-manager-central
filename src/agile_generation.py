"""Source-scoped, typed Agile generation with claim-level support checks."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol

from src.agile import (
    AgileAcceptanceCriterion,
    AgileArtifact,
    AgileArtifactType,
    AgileBehaviorProfile,
    AgileContractError,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
    PARENT_TYPE,
)
from src.agile_profiles import default_profile_selection
from src.agile_prompt_catalog import (
    AgilePromptEnvelope,
    AgilePromptError,
    AgilePromptRequest,
    AgilePromptSource,
    AgilePromptTask,
    MAX_REQUEST_CHARACTERS,
    build_agile_prompt_envelope,
    get_agile_prompt,
    validate_structured_agile_response,
)
from src.claim_support import (
    AssessableClaim,
    ClaimSupportAssessment,
    assess_all_claims,
    extract_assessable_claims,
)
from src.database import DATABASE_FILE, list_retrievable_document_sections
from src.model_controls import (
    DEFAULT_MODEL_CAPABILITIES,
    ModelCapabilities,
    ProviderGenerationSettings,
    RetrievalControls,
    map_profile_generation_settings,
)
from src.models import DocumentStatus, RetrievableDocumentSection
from src.semantic_retrieval import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_MINIMUM_SIMILARITY,
    EmbeddingProvider,
    RetrievalChunk,
    SemanticRetrievalResponse,
    SemanticRetrievalState,
    SemanticRetriever,
    chunk_approved_sections,
)


class AgileGenerationError(ValueError):
    """Raised when trusted controls or provider output fail closed."""


class AgileGenerationState(str, Enum):
    GENERATED = "generated"
    NO_APPROVED_SOURCES = "no_approved_sources"
    NO_RELEVANT_RESULTS = "no_relevant_results"
    SUPPORT_BLOCKED = "support_blocked"


@dataclass(frozen=True)
class AgileParentContext:
    artifact_id: str
    artifact_type: AgileArtifactType
    product_id: int
    title: str

    def as_prompt_data(self) -> str:
        return (
            f"Parent artifact ID: {self.artifact_id}\n"
            f"Parent artifact type: {self.artifact_type.value}\n"
            f"Parent product ID: {self.product_id}\n"
            f"Parent title: {self.title.strip()}"
        )


@dataclass(frozen=True)
class AgileGenerationRequest:
    product_id: int
    selected_document_ids: tuple[int, ...]
    artifact_type: AgileArtifactType
    task: AgilePromptTask
    prompt_id: str
    prompt_version: str
    request_text: str
    profile: object = None
    retrieval_controls: RetrievalControls = RetrievalControls()
    parent: AgileParentContext | None = None


@dataclass(frozen=True)
class MissingRequirement:
    requirement_id: str
    description: str
    source_reference_ids: tuple[str, ...]


@dataclass(frozen=True)
class NonSaveableProposal:
    proposal_id: str
    text: str
    source_gap: str
    unsupported: bool = True
    saveable: bool = False


@dataclass(frozen=True)
class AgileGenerationResult:
    state: AgileGenerationState
    message: str
    artifacts: tuple[AgileArtifact, ...] = ()
    acceptance_criteria: tuple[AgileAcceptanceCriterion, ...] = ()
    claims: tuple[AssessableClaim, ...] = ()
    assessments: tuple[ClaimSupportAssessment, ...] = ()
    missing_requirements: tuple[MissingRequirement, ...] = ()
    proposals: tuple[NonSaveableProposal, ...] = ()
    source_references: tuple[AgileSourceReference, ...] = ()
    profile: AgileBehaviorProfile = AgileBehaviorProfile.STRICTLY_GROUNDED
    prompt_id: str | None = None
    prompt_version: str | None = None
    grounded: bool = False
    requires_human_review: bool = True
    explicitly_accepted: bool = False
    can_save: bool = False


class ScopedRetrievalProvider(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        product_id: int,
        document_ids: tuple[int, ...],
        limit: int,
    ) -> SemanticRetrievalResponse: ...

    def revalidate(self, chunks: tuple[RetrievalChunk, ...]) -> bool: ...


class StructuredGenerationProvider(Protocol):
    def create_structured_response(
        self,
        envelope: AgilePromptEnvelope,
        *,
        json_schema: Mapping[str, object],
        settings: ProviderGenerationSettings,
    ) -> object: ...


class SourceScopedAgileRetriever:
    """Read-only retrieval constrained to one product and selected documents."""

    def __init__(
        self,
        source_loader: Callable[[], list[RetrievableDocumentSection]],
        embedding_provider: EmbeddingProvider,
        *,
        chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
    ) -> None:
        self._source_loader = source_loader
        self._embedding_provider = embedding_provider
        self._chunk_max_characters = chunk_max_characters
        self._minimum_similarity = minimum_similarity

    def _eligible_sections(
        self, product_id: int, document_ids: tuple[int, ...]
    ) -> list[RetrievableDocumentSection]:
        selected = set(document_ids)
        return [
            section
            for section in self._source_loader()
            if section.product_id == product_id
            and section.document_id in selected
            and section.document_status is DocumentStatus.APPROVED
        ]

    def retrieve(
        self,
        query: str,
        *,
        product_id: int,
        document_ids: tuple[int, ...],
        limit: int,
    ) -> SemanticRetrievalResponse:
        retriever = SemanticRetriever(
            lambda: self._eligible_sections(product_id, document_ids),
            self._embedding_provider,
            chunk_max_characters=self._chunk_max_characters,
            minimum_similarity=self._minimum_similarity,
        )
        return retriever.retrieve(query, limit=limit)

    def revalidate(self, chunks: tuple[RetrievalChunk, ...]) -> bool:
        if not chunks:
            return False
        current = {
            chunk.chunk_id: chunk
            for chunk in chunk_approved_sections(
                self._source_loader(), max_characters=self._chunk_max_characters
            )
        }
        return all(current.get(chunk.chunk_id) == chunk for chunk in chunks)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_request(request: AgileGenerationRequest) -> AgileBehaviorProfile:
    if not isinstance(request, AgileGenerationRequest):
        raise AgileGenerationError("A validated Agile generation request is required.")
    if isinstance(request.product_id, bool) or not isinstance(request.product_id, int) or request.product_id <= 0:
        raise AgileGenerationError("Selected product ID is invalid.")
    if not isinstance(request.artifact_type, AgileArtifactType) or not isinstance(request.task, AgilePromptTask):
        raise AgileGenerationError("Select a supported Agile artifact type and task.")
    try:
        get_agile_prompt(
            request.prompt_id,
            request.prompt_version,
            request.task,
            request.artifact_type,
        )
    except AgilePromptError as error:
        raise AgileGenerationError(str(error)) from error
    if (
        not isinstance(request.request_text, str)
        or not request.request_text.strip()
        or len(request.request_text.strip()) > MAX_REQUEST_CHARACTERS
    ):
        raise AgileGenerationError("A valid Product Manager request is required.")
    if not isinstance(request.retrieval_controls, RetrievalControls):
        raise AgileGenerationError("Retrieval controls are invalid.")
    document_ids = tuple(request.selected_document_ids)
    if not document_ids or len(document_ids) != len(set(document_ids)) or any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in document_ids
    ):
        raise AgileGenerationError("Select one or more unique source documents.")
    expected_parent = PARENT_TYPE[request.artifact_type]
    if request.parent is not None:
        if not isinstance(request.parent, AgileParentContext):
            raise AgileGenerationError("Parent context is invalid.")
        required_context_type = (
            request.artifact_type
            if request.task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA
            else expected_parent
        )
        if request.parent.product_id != request.product_id or request.parent.artifact_type is not required_context_type:
            raise AgileGenerationError("Parent context does not match the selected hierarchy and product.")
    if (
        request.task is not AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA
        and expected_parent is None
        and request.parent is not None
    ):
        raise AgileGenerationError("An Epic cannot have a parent.")
    if request.task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA and request.parent is None:
        raise AgileGenerationError("Acceptance-criteria generation requires artifact context.")
    return default_profile_selection(request.profile)


def _prompt_sources(results: Sequence[object]) -> tuple[AgilePromptSource, ...]:
    return tuple(
        AgilePromptSource(
            reference_id=result.chunk.chunk_id,
            product_id=result.chunk.product_id,
            product_name=result.chunk.product_name,
            document_id=result.chunk.document_id,
            document_title=result.chunk.document_title,
            document_type=result.chunk.document_type,
            document_status=result.chunk.document_status,
            section_key=result.chunk.section_key,
            section_title=result.chunk.section_title,
            source_text=result.chunk.text,
        )
        for result in results
    )


def _domain_sources(sources: tuple[AgilePromptSource, ...]) -> dict[str, AgileSourceReference]:
    return {
        source.reference_id: AgileSourceReference(
            reference_id=source.reference_id,
            product_id=source.product_id,
            product_name=source.product_name,
            document_id=source.document_id,
            document_title=source.document_title,
            document_type=source.document_type,
            section_key=source.section_key,
            section_title=source.section_title,
        )
        for source in sources
    }


def _references(ids: object, sources: dict[str, AgileSourceReference]) -> tuple[AgileSourceReference, ...]:
    return tuple(sources[reference_id] for reference_id in sorted(ids))


def _criteria(records: Sequence[Mapping[str, object]], sources: dict[str, AgileSourceReference]) -> tuple[AgileAcceptanceCriterion, ...]:
    return tuple(
        AgileAcceptanceCriterion(
            criterion_id=str(record["criterion_id"]),
            position=int(record["position"]),
            text=str(record["text"]),
            source_references=_references(record["source_reference_ids"], sources),
        )
        for record in records
    )


def _expected_claim_locations(
    artifacts: tuple[AgileArtifact, ...],
    *,
    criteria_only: bool = False,
) -> dict[tuple[str, str], tuple[str, ...]]:
    expected: dict[tuple[str, str], tuple[str, ...]] = {}
    for artifact in artifacts:
        artifact_refs = tuple(source.reference_id for source in artifact.source_references)
        if not criteria_only:
            expected[(artifact.artifact_id, "title")] = artifact_refs
            expected[(artifact.artifact_id, "description")] = artifact_refs
            if artifact.parent_artifact_id is not None:
                expected[(artifact.artifact_id, "parent_relationship")] = artifact_refs
        for criterion in artifact.acceptance_criteria:
            expected[(artifact.artifact_id, f"acceptance_criteria.{criterion.criterion_id}")] = tuple(
                source.reference_id for source in criterion.source_references
            )
    return expected


def _claim_reference_map(
    records: Sequence[Mapping[str, object]],
    artifacts: tuple[AgileArtifact, ...],
    *,
    criteria_only: bool = False,
) -> dict[tuple[str, str], tuple[str, ...]]:
    expected = _expected_claim_locations(artifacts, criteria_only=criteria_only)
    mapped: dict[tuple[str, str], tuple[str, ...]] = {}
    claim_ids: set[str] = set()
    for record in records:
        key = (str(record["artifact_id"]), str(record["location"]).strip())
        claim_id = str(record["claim_id"])
        if key in mapped or claim_id in claim_ids or key not in expected:
            raise AgileGenerationError("Claim mappings are duplicate or do not resolve to generated content.")
        references = tuple(sorted(str(item) for item in record["source_reference_ids"]))
        if not set(references).issubset(expected[key]):
            raise AgileGenerationError("Claim citations must be valid for their artifact or criterion owner.")
        mapped[key] = references
        claim_ids.add(claim_id)
    if set(mapped) != set(expected):
        raise AgileGenerationError("Every generated title, description, relationship, and criterion requires a claim citation mapping.")
    return mapped


class GroundedAgileGenerationService:
    """Generate and assess temporary candidates without any persistence access."""

    def __init__(
        self,
        retrieval_provider: ScopedRetrievalProvider,
        generation_provider: StructuredGenerationProvider,
        *,
        capabilities: ModelCapabilities = DEFAULT_MODEL_CAPABILITIES,
        timestamp_factory: Callable[[], str] = _utc_now,
    ) -> None:
        self._retrieval = retrieval_provider
        self._provider = generation_provider
        self._capabilities = capabilities
        self._timestamp_factory = timestamp_factory

    def generate(self, request: AgileGenerationRequest) -> AgileGenerationResult:
        profile = _validate_request(request)
        settings = map_profile_generation_settings(profile, self._capabilities)
        retrieval = self._retrieval.retrieve(
            request.request_text,
            product_id=request.product_id,
            document_ids=tuple(request.selected_document_ids),
            limit=request.retrieval_controls.top_k,
        )
        if retrieval.state is not SemanticRetrievalState.RESULTS:
            return AgileGenerationResult(
                state=AgileGenerationState(retrieval.state.value),
                message=f"{retrieval.message} No Agile content was generated.",
                profile=profile,
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
            )
        chunks = tuple(result.chunk for result in retrieval.results)
        selected_ids = set(request.selected_document_ids)
        if any(
            chunk.product_id != request.product_id
            or chunk.document_id not in selected_ids
            or chunk.document_status is not DocumentStatus.APPROVED
            for chunk in chunks
        ):
            raise AgileGenerationError("Retrieval returned source content outside the selected Approved scope.")
        if not self._retrieval.revalidate(chunks):
            raise AgileGenerationError("Selected source content changed or became ineligible before generation.")

        sources = _prompt_sources(retrieval.results)
        parent_context = request.parent.as_prompt_data() if request.parent else None
        context_document_ids = tuple(sorted({source.document_id for source in sources}))
        envelope = build_agile_prompt_envelope(
            AgilePromptRequest(
                prompt_id=request.prompt_id,
                prompt_version=request.prompt_version,
                task=request.task,
                artifact_type=request.artifact_type,
                profile=profile,
                product_id=request.product_id,
                selected_document_ids=context_document_ids,
                request_text=request.request_text,
                sources=sources,
                parent_context=parent_context,
            )
        )
        try:
            payload = self._provider.create_structured_response(
                envelope,
                json_schema=envelope.output_contract.json_schema(),
                settings=settings,
            )
        except Exception as error:
            raise AgileGenerationError(
                "The structured generation provider failed; no Agile content was accepted."
            ) from error
        if not self._retrieval.revalidate(chunks):
            raise AgileGenerationError("Selected source content changed or became ineligible during generation.")
        try:
            validated = validate_structured_agile_response(envelope, payload)
            source_records = _domain_sources(sources)
            timestamp = self._timestamp_factory()
            if "artifacts" in validated:
                artifacts = tuple(
                    AgileArtifact(
                        artifact_id=str(record["artifact_id"]),
                        artifact_type=AgileArtifactType(record["artifact_type"]),
                        product_id=int(record["product_id"]),
                        title=str(record["title"]),
                        description=str(record["description"]),
                        parent_artifact_id=record["parent_artifact_id"],
                        position=int(record["position"]),
                        acceptance_criteria=_criteria(record["acceptance_criteria"], source_records),
                        source_references=_references(record["source_reference_ids"], source_records),
                        created_at=timestamp,
                        updated_at=timestamp,
                        review_state=AgileReviewState.PENDING_REVIEW,
                        provenance=ContentProvenance.AI_GENERATED,
                    )
                    for record in validated["artifacts"]
                )
            else:
                criteria = _criteria(validated["acceptance_criteria"], source_records)
                if request.parent is None:
                    raise AgileGenerationError(
                        "Acceptance-criteria generation lost its validated artifact context."
                    )
                artifacts = (
                    AgileArtifact(
                        artifact_id=request.parent.artifact_id,
                        artifact_type=request.parent.artifact_type,
                        product_id=request.product_id,
                        title=request.parent.title,
                        description=request.parent.title,
                        acceptance_criteria=criteria,
                        source_references=tuple(
                            sorted(
                                {source for criterion in criteria for source in criterion.source_references},
                                key=lambda source: source.reference_id,
                            )
                        ),
                        position=1,
                        created_at=timestamp,
                        updated_at=timestamp,
                    ),
                )
            for artifact in artifacts:
                expected_parent_id = request.parent.artifact_id if request.parent and request.task is not AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA else None
                if request.task is not AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA and artifact.parent_artifact_id != expected_parent_id:
                    raise AgileGenerationError("Generated parent relationships do not match the validated parent context.")
            criteria_only = request.task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA
            claim_map = _claim_reference_map(
                validated["claim_to_source_references"],
                artifacts,
                criteria_only=criteria_only,
            )
            claims = extract_assessable_claims(artifacts, claim_map)
            if criteria_only:
                claims = tuple(
                    claim
                    for claim in claims
                    if claim.location.startswith("acceptance_criteria.")
                )
            assessments = assess_all_claims(claims, sources)
        except (AgilePromptError, AgileContractError, KeyError, TypeError, ValueError) as error:
            if isinstance(error, AgileGenerationError):
                raise
            raise AgileGenerationError("The structured Agile response is invalid and was rejected.") from error

        missing = tuple(
            MissingRequirement(
                requirement_id=str(item["requirement_id"]),
                description=str(item["description"]).strip(),
                source_reference_ids=tuple(sorted(str(value) for value in item["source_reference_ids"])),
            )
            for item in validated["missing_requirements"]
        )
        proposals = tuple(
            NonSaveableProposal(
                proposal_id=str(item["proposal_id"]),
                text=str(item["text"]).strip(),
                source_gap=str(item["source_gap"]).strip(),
            )
            for item in validated["proposals"]
        )
        if proposals and profile is not AgileBehaviorProfile.EXPLORATORY:
            raise AgileGenerationError("Only Exploratory may return labeled non-saveable proposals.")
        safe = all(assessment.supported for assessment in assessments) and not missing and not proposals
        return AgileGenerationResult(
            state=AgileGenerationState.GENERATED if safe else AgileGenerationState.SUPPORT_BLOCKED,
            message=(
                "Grounded Agile candidates are ready for later human review; nothing was saved."
                if safe
                else "Agile candidates contain unresolved support findings or source gaps and are blocked; nothing was saved."
            ),
            artifacts=artifacts if "artifacts" in validated else (),
            acceptance_criteria=(artifacts[0].acceptance_criteria if "artifacts" not in validated else ()),
            claims=claims,
            assessments=assessments,
            missing_requirements=missing,
            proposals=proposals,
            source_references=tuple(source_records[key] for key in sorted(source_records)),
            profile=profile,
            prompt_id=envelope.prompt.prompt_id,
            prompt_version=envelope.prompt.version,
            grounded=safe,
        )


class DatabaseGroundedAgileGenerationService(GroundedAgileGenerationService):
    """Database-backed read-only retrieval with injected offline-capable providers."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        generation_provider: StructuredGenerationProvider,
        database_path: str | Path = DATABASE_FILE,
        *,
        capabilities: ModelCapabilities = DEFAULT_MODEL_CAPABILITIES,
        chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
        timestamp_factory: Callable[[], str] = _utc_now,
    ) -> None:
        retrieval = SourceScopedAgileRetriever(
            lambda: list_retrievable_document_sections(database_path),
            embedding_provider,
            chunk_max_characters=chunk_max_characters,
            minimum_similarity=minimum_similarity,
        )
        super().__init__(
            retrieval,
            generation_provider,
            capabilities=capabilities,
            timestamp_factory=timestamp_factory,
        )
