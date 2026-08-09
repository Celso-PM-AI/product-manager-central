"""Deterministic offline scoring for the completed Phase 9 RAG workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from src.grounded_generation import (
    GenerationCitation,
    GroundedGenerationResult,
    GroundedGenerationState,
)
from src.models import DocumentStatus, DocumentType
from src.semantic_retrieval import (
    RetrievalChunk,
    SemanticRetrievalResponse,
    SemanticRetrievalState,
)


RELEASE_MINIMUM_OVERALL_SCORE: Final[float] = 80.0


@dataclass(frozen=True)
class Phase9EvaluationCase:
    """Observed workflow outcome plus deterministic expected retrieval results."""

    name: str
    expected_chunk_ids: frozenset[str]
    retrieval: SemanticRetrievalResponse
    generation: GroundedGenerationResult
    grounding_expected: bool
    human_control_preserved: bool
    source_separation_preserved: bool


@dataclass(frozen=True)
class Phase9EvaluationScores:
    """Normalized criterion scores and the unweighted 0-100 overall score."""

    retrieval_precision: float
    retrieval_recall: float
    source_trust: float
    citation_completeness: float
    citation_correspondence: float
    grounded_generation: float
    human_control: float
    source_separation: float

    @property
    def criteria(self) -> tuple[float, ...]:
        return (
            self.retrieval_precision,
            self.retrieval_recall,
            self.source_trust,
            self.citation_completeness,
            self.citation_correspondence,
            self.grounded_generation,
            self.human_control,
            self.source_separation,
        )

    @property
    def overall_score(self) -> float:
        return 100.0 * sum(self.criteria) / len(self.criteria)


@dataclass(frozen=True)
class Phase9EvaluationReport:
    """One reproducible evaluation result and its release-gate decision."""

    case_name: str
    scores: Phase9EvaluationScores
    release_passed: bool


@dataclass(frozen=True)
class Phase9EvaluationSuiteReport:
    """Aggregate criterion means for a deterministic release-evaluation suite."""

    cases: tuple[Phase9EvaluationReport, ...]
    scores: Phase9EvaluationScores
    release_passed: bool


def _retrieval_scores(
    expected_chunk_ids: frozenset[str],
    retrieval: SemanticRetrievalResponse,
) -> tuple[float, float]:
    returned_chunk_ids = {result.chunk.chunk_id for result in retrieval.results}
    if not expected_chunk_ids and not returned_chunk_ids:
        return 1.0, 1.0
    if not expected_chunk_ids or not returned_chunk_ids:
        return 0.0, 0.0
    matching = len(expected_chunk_ids & returned_chunk_ids)
    return (
        matching / len(returned_chunk_ids),
        matching / len(expected_chunk_ids),
    )


def _source_is_trusted(chunk: RetrievalChunk) -> bool:
    return (
        chunk.document_status is DocumentStatus.APPROVED
        and chunk.document_type in {DocumentType.BRD, DocumentType.PRD}
        and chunk.product_id > 0
        and bool(chunk.product_name.strip())
        and chunk.document_id > 0
        and bool(chunk.document_title.strip())
        and bool(chunk.section_key.strip())
        and bool(chunk.section_title.strip())
        and bool(chunk.text.strip())
    )


def _citation_is_complete(citation: GenerationCitation) -> bool:
    return (
        citation.source_number > 0
        and citation.product_id > 0
        and bool(citation.product.strip())
        and citation.document_id > 0
        and bool(citation.document_title.strip())
        and citation.document_type in {DocumentType.BRD, DocumentType.PRD}
        and bool(citation.section_key.strip())
        and bool(citation.section.strip())
    )


def _citation_matches_chunk(
    citation: GenerationCitation,
    chunk: RetrievalChunk,
) -> bool:
    return (
        citation.product_id == chunk.product_id
        and citation.product == chunk.product_name
        and citation.document_id == chunk.document_id
        and citation.document_title == chunk.document_title
        and citation.document_type is chunk.document_type
        and citation.section_key == chunk.section_key
        and citation.section == chunk.section_title
    )


def _citation_scores(
    generation: GroundedGenerationResult,
    retrieval: SemanticRetrievalResponse,
    *,
    grounding_expected: bool,
) -> tuple[float, float]:
    citations = generation.citations
    results = retrieval.results
    if not grounding_expected:
        score = 1.0 if not citations else 0.0
        return score, score

    denominator = max(len(citations), len(results), 1)
    complete = sum(_citation_is_complete(citation) for citation in citations)
    corresponding = sum(
        _citation_matches_chunk(citation, result.chunk)
        for citation, result in zip(citations, results)
    )
    return complete / denominator, corresponding / denominator


def _grounding_score(
    generation: GroundedGenerationResult,
    retrieval: SemanticRetrievalResponse,
    *,
    grounding_expected: bool,
) -> float:
    if grounding_expected:
        passed = (
            retrieval.state is SemanticRetrievalState.RESULTS
            and bool(retrieval.results)
            and generation.state is GroundedGenerationState.GENERATED_DRAFT
            and generation.grounded
            and bool(generation.content and generation.content.strip())
            and bool(generation.citations)
            and generation.is_generated_draft
            and generation.requires_human_review
            and not generation.explicitly_accepted
            and not generation.can_save
        )
    else:
        passed = (
            retrieval.state is not SemanticRetrievalState.RESULTS
            and not retrieval.results
            and generation.state
            in {
                GroundedGenerationState.NO_APPROVED_SOURCES,
                GroundedGenerationState.NO_RELEVANT_RESULTS,
            }
            and not generation.grounded
            and generation.content is None
            and not generation.citations
            and generation.requires_human_review
            and not generation.explicitly_accepted
            and not generation.can_save
        )
    return float(passed)


def evaluate_phase9_case(case: Phase9EvaluationCase) -> Phase9EvaluationReport:
    """Score one offline case without network, persistence, or source mutation."""

    if not isinstance(case.name, str) or not case.name.strip():
        raise ValueError("An evaluation case needs a name.")

    precision, recall = _retrieval_scores(case.expected_chunk_ids, case.retrieval)
    completeness, correspondence = _citation_scores(
        case.generation,
        case.retrieval,
        grounding_expected=case.grounding_expected,
    )
    scores = Phase9EvaluationScores(
        retrieval_precision=precision,
        retrieval_recall=recall,
        source_trust=float(
            all(_source_is_trusted(result.chunk) for result in case.retrieval.results)
        ),
        citation_completeness=completeness,
        citation_correspondence=correspondence,
        grounded_generation=_grounding_score(
            case.generation,
            case.retrieval,
            grounding_expected=case.grounding_expected,
        ),
        human_control=float(case.human_control_preserved),
        source_separation=float(case.source_separation_preserved),
    )
    release_passed = _release_passed(scores)
    return Phase9EvaluationReport(case.name.strip(), scores, release_passed)


def _release_passed(scores: Phase9EvaluationScores) -> bool:
    return (
        scores.overall_score >= RELEASE_MINIMUM_OVERALL_SCORE
        and scores.source_trust == 1.0
        and scores.citation_completeness == 1.0
        and scores.human_control == 1.0
        and scores.source_separation == 1.0
    )


def evaluate_phase9_suite(
    cases: tuple[Phase9EvaluationCase, ...],
) -> Phase9EvaluationSuiteReport:
    """Average each criterion equally across cases, then apply release gates."""

    if not cases:
        raise ValueError("A Phase 9 evaluation suite needs at least one case.")
    reports = tuple(evaluate_phase9_case(case) for case in cases)
    criterion_names = tuple(Phase9EvaluationScores.__dataclass_fields__)
    means = {
        name: sum(getattr(report.scores, name) for report in reports) / len(reports)
        for name in criterion_names
    }
    scores = Phase9EvaluationScores(**means)
    return Phase9EvaluationSuiteReport(reports, scores, _release_passed(scores))
