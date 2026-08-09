"""Tests for deterministic Phase 9 RAG evaluation and release scoring."""

import unittest
from dataclasses import replace

from src.grounded_generation import (
    GenerationCitation,
    GroundedGenerationResult,
    GroundedGenerationState,
)
from src.models import DocumentStatus, DocumentType
from src.rag_evaluation import (
    Phase9EvaluationCase,
    evaluate_phase9_case,
    evaluate_phase9_suite,
)
from src.semantic_retrieval import (
    RetrievalChunk,
    SemanticRetrievalResponse,
    SemanticRetrievalResult,
    SemanticRetrievalState,
)


def chunk(number: int, *, status=DocumentStatus.APPROVED) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=f"stable-chunk-{number}",
        chunk_index=0,
        text=f"Approved evidence {number}.",
        product_id=7,
        product_name="Atlas",
        document_id=number,
        document_title=f"Atlas PRD {number}",
        document_type=DocumentType.PRD,
        document_status=status,
        section_key="product_overview",
        section_title="Product overview",
    )


def retrieval(*chunks: RetrievalChunk) -> SemanticRetrievalResponse:
    return SemanticRetrievalResponse(
        SemanticRetrievalState.RESULTS,
        "Found approved evidence.",
        tuple(
            SemanticRetrievalResult(item, 1.0 - index / 10)
            for index, item in enumerate(chunks)
        ),
    )


def citation(source_number: int, source: RetrievalChunk) -> GenerationCitation:
    return GenerationCitation(
        source_number=source_number,
        product_id=source.product_id,
        product=source.product_name,
        document_id=source.document_id,
        document_title=source.document_title,
        document_type=source.document_type,
        section_key=source.section_key,
        section=source.section_title,
    )


def generation(*sources: RetrievalChunk) -> GroundedGenerationResult:
    return GroundedGenerationResult(
        GroundedGenerationState.GENERATED_DRAFT,
        "Ready for review.",
        "Generated content [Source 1]",
        tuple(citation(index, source) for index, source in enumerate(sources, 1)),
        True,
    )


def evaluation_case(
    returned: tuple[RetrievalChunk, ...],
    *,
    expected: frozenset[str] | None = None,
    generated: GroundedGenerationResult | None = None,
    grounding_expected: bool = True,
    human_control: bool = True,
    source_separation: bool = True,
) -> Phase9EvaluationCase:
    return Phase9EvaluationCase(
        name="deterministic case",
        expected_chunk_ids=(
            frozenset(item.chunk_id for item in returned)
            if expected is None
            else expected
        ),
        retrieval=retrieval(*returned),
        generation=generated or generation(*returned),
        grounding_expected=grounding_expected,
        human_control_preserved=human_control,
        source_separation_preserved=source_separation,
    )


class Phase9EvaluationScoringTests(unittest.TestCase):
    def test_perfect_case_scores_100_and_passes_every_release_gate(self):
        sources = (chunk(1), chunk(2))

        first = evaluate_phase9_case(evaluation_case(sources))
        second = evaluate_phase9_case(evaluation_case(sources))

        self.assertEqual(first, second)
        self.assertEqual(first.scores.criteria, (1.0,) * 8)
        self.assertEqual(first.scores.overall_score, 100.0)
        self.assertTrue(first.release_passed)

    def test_precision_and_recall_use_expected_and_returned_stable_chunk_ids(self):
        expected_one = chunk(1)
        expected_two = chunk(2)
        unexpected = chunk(3)

        report = evaluate_phase9_case(
            evaluation_case(
                (expected_one, unexpected),
                expected=frozenset(
                    (expected_one.chunk_id, expected_two.chunk_id)
                ),
            )
        )

        self.assertEqual(report.scores.retrieval_precision, 0.5)
        self.assertEqual(report.scores.retrieval_recall, 0.5)
        self.assertEqual(report.scores.overall_score, 87.5)
        self.assertTrue(report.release_passed)

    def test_empty_expected_and_returned_results_are_a_successful_boundary(self):
        empty_retrieval = SemanticRetrievalResponse(
            SemanticRetrievalState.NO_APPROVED_SOURCES,
            "No approved BRD or PRD sources are available.",
            (),
        )
        empty_generation = GroundedGenerationResult(
            GroundedGenerationState.NO_APPROVED_SOURCES,
            "No grounded draft was generated.",
            None,
            (),
            False,
        )
        case = Phase9EvaluationCase(
            "approved-source empty state",
            frozenset(),
            empty_retrieval,
            empty_generation,
            False,
            True,
            True,
        )

        report = evaluate_phase9_case(case)

        self.assertEqual(report.scores.criteria, (1.0,) * 8)
        self.assertTrue(report.release_passed)

    def test_unexpected_results_for_an_empty_expectation_score_zero(self):
        source = chunk(1)

        report = evaluate_phase9_case(
            evaluation_case((source,), expected=frozenset())
        )

        self.assertEqual(report.scores.retrieval_precision, 0.0)
        self.assertEqual(report.scores.retrieval_recall, 0.0)

    def test_citations_are_scored_fractionally_for_metadata_and_correspondence(self):
        first, second = chunk(1), chunk(2)
        generated = generation(first, second)
        incomplete = replace(generated.citations[1], section="")
        mismatched = replace(incomplete, document_id=999)
        generated = replace(
            generated,
            citations=(generated.citations[0], mismatched),
        )

        report = evaluate_phase9_case(
            evaluation_case((first, second), generated=generated)
        )

        self.assertEqual(report.scores.citation_completeness, 0.5)
        self.assertEqual(report.scores.citation_correspondence, 0.5)
        self.assertFalse(report.release_passed)

    def test_untrusted_source_fails_release_even_when_overall_is_above_80(self):
        untrusted = chunk(1, status=DocumentStatus.DRAFT)

        report = evaluate_phase9_case(evaluation_case((untrusted,)))

        self.assertEqual(report.scores.source_trust, 0.0)
        self.assertEqual(report.scores.overall_score, 87.5)
        self.assertFalse(report.release_passed)

    def test_human_control_and_source_separation_are_mandatory_release_gates(self):
        source = chunk(1)

        for human_control, source_separation in ((False, True), (True, False)):
            with self.subTest(
                human_control=human_control,
                source_separation=source_separation,
            ):
                report = evaluate_phase9_case(
                    evaluation_case(
                        (source,),
                        human_control=human_control,
                        source_separation=source_separation,
                    )
                )
                self.assertEqual(report.scores.overall_score, 87.5)
                self.assertFalse(report.release_passed)

    def test_grounding_requires_safe_generated_or_ungrounded_state(self):
        source = chunk(1)
        unsafe = replace(generation(source), can_save=True)

        report = evaluate_phase9_case(
            evaluation_case((source,), generated=unsafe)
        )

        self.assertEqual(report.scores.grounded_generation, 0.0)
        self.assertEqual(report.scores.overall_score, 87.5)
        self.assertTrue(report.release_passed)

    def test_suite_averages_each_criterion_and_applies_safety_gates(self):
        trusted = evaluation_case((chunk(1),))
        untrusted = evaluation_case((chunk(2, status=DocumentStatus.DRAFT),))

        report = evaluate_phase9_suite((trusted, untrusted))

        self.assertEqual(report.scores.source_trust, 0.5)
        self.assertEqual(report.scores.overall_score, 93.75)
        self.assertFalse(report.release_passed)

    def test_empty_suite_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one case"):
            evaluate_phase9_suite(())

    def test_case_name_is_required(self):
        source = chunk(1)

        with self.assertRaisesRegex(ValueError, "needs a name"):
            evaluate_phase9_case(replace(evaluation_case((source,)), name=" "))


if __name__ == "__main__":
    unittest.main()
