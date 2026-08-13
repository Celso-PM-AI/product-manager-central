"""Offline evaluation metrics for grounded Agile generation."""

from __future__ import annotations

from dataclasses import dataclass

from src.agile import AgileBehaviorProfile
from src.agile_generation import AgileGenerationResult


@dataclass(frozen=True)
class AgileEvaluationReport:
    case_name: str
    retrieval_precision: float
    retrieval_recall: float
    artifact_traceability: float
    criterion_traceability: float
    unsupported_claim_recall: float
    false_positive_claim_ids: tuple[str, ...]
    missing_requirement_recall: float
    profile_conformant: bool


def _recall(expected: set[str], returned: set[str]) -> float:
    return 1.0 if not expected else len(expected & returned) / len(expected)


def evaluate_agile_generation_case(
    case_name: str,
    result: AgileGenerationResult,
    *,
    expected_source_reference_ids: set[str],
    expected_unsupported_claim_ids: set[str],
    expected_missing_requirement_ids: set[str],
) -> AgileEvaluationReport:
    """Score one deterministic fixture without a provider or LLM judge."""

    if not isinstance(case_name, str) or not case_name.strip():
        raise ValueError("Evaluation case name is required.")
    if not isinstance(result, AgileGenerationResult):
        raise ValueError("A grounded Agile generation result is required.")
    returned_sources = {
        reference.reference_id for reference in result.source_references
    }
    precision = (
        1.0
        if not returned_sources and not expected_source_reference_ids
        else (
            len(returned_sources & expected_source_reference_ids) / len(returned_sources)
            if returned_sources
            else 0.0
        )
    )
    artifact_total = len(result.artifacts)
    criterion_records = tuple(
        criterion
        for artifact in result.artifacts
        for criterion in artifact.acceptance_criteria
    ) or result.acceptance_criteria
    unsafe_claim_ids = {
        assessment.claim.claim_id
        for assessment in result.assessments
        if not assessment.supported
    }
    returned_missing = {
        requirement.requirement_id for requirement in result.missing_requirements
    }
    profile_conformant = all(
        proposal.unsupported and not proposal.saveable for proposal in result.proposals
    ) and (
        result.profile is AgileBehaviorProfile.EXPLORATORY or not result.proposals
    )
    return AgileEvaluationReport(
        case_name=case_name.strip(),
        retrieval_precision=precision,
        retrieval_recall=_recall(expected_source_reference_ids, returned_sources),
        artifact_traceability=(
            1.0
            if artifact_total == 0
            else sum(bool(item.source_references) for item in result.artifacts)
            / artifact_total
        ),
        criterion_traceability=(
            1.0
            if not criterion_records
            else sum(bool(item.source_references) for item in criterion_records)
            / len(criterion_records)
        ),
        unsupported_claim_recall=_recall(
            expected_unsupported_claim_ids, unsafe_claim_ids
        ),
        false_positive_claim_ids=tuple(
            sorted(unsafe_claim_ids - expected_unsupported_claim_ids)
        ),
        missing_requirement_recall=_recall(
            expected_missing_requirement_ids, returned_missing
        ),
        profile_conformant=profile_conformant,
    )
