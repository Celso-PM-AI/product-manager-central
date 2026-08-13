"""Deterministic claim extraction and conservative source-support assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Final

from src.agile import AgileArtifact
from src.agile_prompt_catalog import AgilePromptSource


class ClaimSupportOutcome(str, Enum):
    """Approved Checkpoint 9 support outcomes."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    MISSING_SOURCE = "missing_source"


class ClaimSupportReason(str, Enum):
    """Deterministic reasons nested under the approved support outcomes."""

    DIRECT_TEXT_SUPPORT = "direct_text_support"
    CONTRADICTED_BY_SOURCE = "contradicted_by_source"
    PARTIAL_OR_AMBIGUOUS_MATCH = "partial_or_ambiguous_match"
    NO_SOURCE_CORRESPONDENCE = "no_source_correspondence"
    UNCITED_CLAIM = "uncited_claim"
    UNRESOLVED_CITATION = "unresolved_citation"


ASSESSMENT_METHOD: Final[str] = "deterministic-conservative-text-correspondence-v1"


@dataclass(frozen=True)
class AssessableClaim:
    """One stable field-level claim owned by an artifact or criterion."""

    claim_id: str
    artifact_id: str
    owner_id: str
    location: str
    text: str
    source_reference_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClaimSupportAssessment:
    """Auditable result; deterministic text correspondence is not semantic truth."""

    claim: AssessableClaim
    outcome: ClaimSupportOutcome
    reason: ClaimSupportReason
    evidence: tuple[str, ...]
    assessment_method: str = ASSESSMENT_METHOD
    deterministic: bool = True
    semantic_guarantee: bool = False

    @property
    def supported(self) -> bool:
        return self.outcome is ClaimSupportOutcome.SUPPORTED


def _stable_claim_id(artifact_id: str, location: str, text: str) -> str:
    digest = hashlib.sha256(
        f"{artifact_id}\x1f{location}\x1f{text}".encode("utf-8")
    ).hexdigest()[:20]
    return f"claim-{digest}"


def extract_assessable_claims(
    artifacts: tuple[AgileArtifact, ...],
    claim_references: dict[tuple[str, str], tuple[str, ...]],
) -> tuple[AssessableClaim, ...]:
    """Extract title, description, relationship, and criterion claims in order."""

    claims: list[AssessableClaim] = []
    for artifact in artifacts:
        fields: list[tuple[str, str, str]] = [
            ("title", artifact.artifact_id, artifact.title),
            ("description", artifact.artifact_id, artifact.description),
        ]
        if artifact.parent_artifact_id is not None:
            fields.append(
                (
                    "parent_relationship",
                    artifact.artifact_id,
                    (
                        f"{artifact.artifact_id} is a {artifact.artifact_type.value} "
                        f"under {artifact.parent_artifact_id}."
                    ),
                )
            )
        fields.extend(
            (
                f"acceptance_criteria.{criterion.criterion_id}",
                criterion.criterion_id,
                criterion.text,
            )
            for criterion in artifact.acceptance_criteria
        )
        for location, owner_id, text in fields:
            references = claim_references.get((artifact.artifact_id, location), ())
            claims.append(
                AssessableClaim(
                    claim_id=_stable_claim_id(artifact.artifact_id, location, text),
                    artifact_id=artifact.artifact_id,
                    owner_id=owner_id,
                    location=location,
                    text=text,
                    source_reference_ids=tuple(sorted(references)),
                )
            )
    return tuple(claims)


_SPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*")
_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {"a", "an", "and", "as", "at", "be", "by", "for", "in", "is", "of", "on", "or", "the", "to"}
)


def _normalize(value: str) -> str:
    return _SPACE.sub(" ", value.casefold()).strip(" .,:;!?\n\t")


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(_normalize(value))
        if token not in _STOP_WORDS and len(token) > 1
    }


def _opposite_phrases(claim: str) -> tuple[str, ...]:
    normalized = _normalize(claim)
    opposites: list[str] = []
    for positive, negative in ((" must ", " must not "), (" is ", " is not "), (" can ", " cannot ")):
        padded = f" {normalized} "
        if negative in padded:
            opposites.append(padded.replace(negative, positive, 1).strip())
        elif positive in padded:
            opposites.append(padded.replace(positive, negative, 1).strip())
    return tuple(opposites)


def assess_claim_support(
    claim: AssessableClaim,
    sources_by_reference: dict[str, AgilePromptSource],
) -> ClaimSupportAssessment:
    """Conservatively assess one claim without treating citation/keywords as proof."""

    if not claim.source_reference_ids:
        return ClaimSupportAssessment(
            claim,
            ClaimSupportOutcome.MISSING_SOURCE,
            ClaimSupportReason.UNCITED_CLAIM,
            (),
        )
    unresolved = tuple(
        reference_id
        for reference_id in claim.source_reference_ids
        if reference_id not in sources_by_reference
    )
    if unresolved:
        return ClaimSupportAssessment(
            claim,
            ClaimSupportOutcome.MISSING_SOURCE,
            ClaimSupportReason.UNRESOLVED_CITATION,
            unresolved,
        )

    normalized_claim = _normalize(claim.text)
    cited_sources = tuple(
        sources_by_reference[reference_id]
        for reference_id in claim.source_reference_ids
    )
    for source in cited_sources:
        normalized_source = _normalize(source.source_text)
        if normalized_claim and normalized_claim in normalized_source:
            return ClaimSupportAssessment(
                claim,
                ClaimSupportOutcome.SUPPORTED,
                ClaimSupportReason.DIRECT_TEXT_SUPPORT,
                (source.reference_id,),
            )
    opposites = _opposite_phrases(claim.text)
    for source in cited_sources:
        normalized_source = _normalize(source.source_text)
        if any(opposite in normalized_source for opposite in opposites):
            return ClaimSupportAssessment(
                claim,
                ClaimSupportOutcome.UNSUPPORTED,
                ClaimSupportReason.CONTRADICTED_BY_SOURCE,
                (source.reference_id,),
            )

    claim_tokens = _tokens(claim.text)
    best_reference: str | None = None
    best_coverage = 0.0
    if len(claim_tokens) >= 3:
        for source in cited_sources:
            coverage = len(claim_tokens & _tokens(source.source_text)) / len(claim_tokens)
            if coverage > best_coverage:
                best_reference, best_coverage = source.reference_id, coverage
    if best_reference is not None and best_coverage >= 0.8:
        return ClaimSupportAssessment(
            claim,
            ClaimSupportOutcome.AMBIGUOUS,
            ClaimSupportReason.PARTIAL_OR_AMBIGUOUS_MATCH,
            (best_reference, f"token_coverage={best_coverage:.3f}"),
        )
    return ClaimSupportAssessment(
        claim,
        ClaimSupportOutcome.UNSUPPORTED,
        ClaimSupportReason.NO_SOURCE_CORRESPONDENCE,
        (),
    )


def assess_all_claims(
    claims: tuple[AssessableClaim, ...],
    sources: tuple[AgilePromptSource, ...],
) -> tuple[ClaimSupportAssessment, ...]:
    """Assess claims in stable extraction order against only cited context sources."""

    sources_by_reference = {source.reference_id: source for source in sources}
    return tuple(assess_claim_support(claim, sources_by_reference) for claim in claims)
