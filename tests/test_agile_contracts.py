"""Focused tests for the Checkpoint 7 Agile domain contracts."""

from dataclasses import replace
import unittest

from src.agile import (
    AgileAcceptanceCriterion,
    AgileArtifact,
    AgileArtifactBatch,
    AgileArtifactType,
    AgileBehaviorProfile,
    AgileContractError,
    AgileReviewState,
    AgileSourceReference,
    ContentProvenance,
)
from src.models import DocumentType


TIMESTAMP = "2026-08-11T10:00:00.000000Z"


def source(product_id: int = 1, reference_id: str = "source-1") -> AgileSourceReference:
    return AgileSourceReference(
        reference_id=reference_id,
        product_id=product_id,
        product_name="Atlas",
        document_id=10,
        document_title="Atlas PRD",
        document_type=DocumentType.PRD,
        section_key="problem_statement",
        section_title="Problem Statement",
    )


def artifact(
    artifact_type: AgileArtifactType,
    position: int,
    *,
    parent_id: str | None = None,
    product_id: int = 1,
    review_state: AgileReviewState = AgileReviewState.PENDING_REVIEW,
) -> AgileArtifact:
    artifact_id = f"artifact-{position}"
    criterion = AgileAcceptanceCriterion(
        criterion_id=f"criterion-{position}",
        position=1,
        text=f"The outcome for artifact {position} is observable.",
        source_references=(source(product_id),),
    )
    return AgileArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        product_id=product_id,
        title=f"Artifact {position}",
        description="A grounded Agile artifact.",
        acceptance_criteria=(criterion,),
        source_references=(source(product_id),),
        position=position,
        parent_artifact_id=parent_id,
        review_state=review_state,
        provenance=ContentProvenance.AI_GENERATED,
        revision=1,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def batch(*artifacts: AgileArtifact, product_id: int = 1) -> AgileArtifactBatch:
    return AgileArtifactBatch(
        batch_id="batch-1",
        product_id=product_id,
        behavior_profile=AgileBehaviorProfile.STRICTLY_GROUNDED,
        review_state=AgileReviewState.PENDING_REVIEW,
        prompt_version="1.0.0",
        artifacts=tuple(artifacts),
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


class AgileTypeAndHierarchyTests(unittest.TestCase):
    def test_enums_contain_only_approved_values(self):
        self.assertEqual(
            [item.value for item in AgileArtifactType],
            ["epic", "capability", "feature", "user_story"],
        )
        self.assertEqual(
            [item.value for item in ContentProvenance],
            ["ai_generated", "product_manager_edited"],
        )

    def test_every_artifact_type_can_be_created_without_a_parent(self):
        for artifact_type in AgileArtifactType:
            with self.subTest(artifact_type=artifact_type):
                created = artifact(artifact_type, 1)
                batch(created)
                self.assertIsNone(created.parent_artifact_id)

    def test_complete_approved_hierarchy_is_valid(self):
        artifacts = (
            artifact(AgileArtifactType.EPIC, 1),
            artifact(AgileArtifactType.CAPABILITY, 2, parent_id="artifact-1"),
            artifact(AgileArtifactType.FEATURE, 3, parent_id="artifact-2"),
            artifact(AgileArtifactType.USER_STORY, 4, parent_id="artifact-3"),
        )
        self.assertEqual(batch(*artifacts).artifacts, artifacts)

    def test_every_disallowed_parent_child_type_is_rejected(self):
        allowed = {
            AgileArtifactType.CAPABILITY: AgileArtifactType.EPIC,
            AgileArtifactType.FEATURE: AgileArtifactType.CAPABILITY,
            AgileArtifactType.USER_STORY: AgileArtifactType.FEATURE,
        }
        for child_type in AgileArtifactType:
            for parent_type in AgileArtifactType:
                if allowed.get(child_type) is parent_type:
                    continue
                with self.subTest(child=child_type, parent=parent_type):
                    parent = artifact(parent_type, 1)
                    if child_type is AgileArtifactType.EPIC:
                        with self.assertRaises(AgileContractError):
                            artifact(child_type, 2, parent_id=parent.artifact_id)
                    else:
                        child = artifact(child_type, 2, parent_id=parent.artifact_id)
                        with self.assertRaises(AgileContractError):
                            batch(parent, child)

    def test_missing_late_and_cross_product_parents_are_rejected(self):
        missing_parent = artifact(
            AgileArtifactType.FEATURE, 1, parent_id="not-in-batch"
        )
        with self.assertRaises(AgileContractError):
            batch(missing_parent)

        child = artifact(AgileArtifactType.CAPABILITY, 1, parent_id="artifact-2")
        parent = artifact(AgileArtifactType.EPIC, 2)
        with self.assertRaises(AgileContractError):
            batch(child, parent)

        with self.assertRaises(AgileContractError):
            batch(artifact(AgileArtifactType.EPIC, 1, product_id=2))


class AcceptanceCriteriaAndFieldTests(unittest.TestCase):
    def test_criterion_is_structured_ordered_and_traceable(self):
        criterion = AgileAcceptanceCriterion(
            criterion_id="criterion-a",
            position=1,
            text="The user can observe the saved result.",
            source_references=(source(),),
        )
        self.assertEqual(criterion.position, 1)
        self.assertEqual(criterion.source_references[0].document_type, DocumentType.PRD)

    def test_empty_malformed_duplicate_and_unordered_criteria_are_rejected(self):
        valid = artifact(AgileArtifactType.EPIC, 1)
        with self.assertRaises(AgileContractError):
            replace(valid, acceptance_criteria=())
        with self.assertRaises(AgileContractError):
            replace(valid.acceptance_criteria[0], text="  ")
        with self.assertRaises(AgileContractError):
            replace(valid.acceptance_criteria[0], position=0)

        first = valid.acceptance_criteria[0]
        duplicate_id = replace(first, text="A second observable result.")
        with self.assertRaises(AgileContractError):
            replace(valid, acceptance_criteria=(first, duplicate_id))
        duplicate_text = replace(first, criterion_id="criterion-other", text=first.text.upper())
        with self.assertRaises(AgileContractError):
            replace(valid, acceptance_criteria=(first, duplicate_text))
        unordered = replace(first, criterion_id="criterion-other", position=3)
        with self.assertRaises(AgileContractError):
            replace(valid, acceptance_criteria=(first, unordered))

    def test_required_ids_text_sources_and_enum_types_are_validated(self):
        valid = artifact(AgileArtifactType.EPIC, 1)
        for field_name, invalid in (
            ("artifact_id", "bad id"),
            ("title", " "),
            ("description", None),
            ("position", 0),
            ("revision", 0),
            ("created_at", "not-a-timestamp"),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaises(AgileContractError):
                    replace(valid, **{field_name: invalid})
        with self.assertRaises(AgileContractError):
            replace(valid, artifact_type="epic")
        with self.assertRaises(AgileContractError):
            replace(valid, source_references=())

    def test_traceability_requires_product_document_and_section_context(self):
        for field_name, invalid in (
            ("product_id", 0),
            ("product_name", ""),
            ("document_id", -1),
            ("document_title", " "),
            ("section_key", ""),
            ("section_title", None),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaises(AgileContractError):
                    replace(source(), **{field_name: invalid})
        with self.assertRaises(AgileContractError):
            replace(source(), document_type="PRD")

    def test_lifecycle_timestamp_provenance_and_revision_rules(self):
        accepted_artifact = replace(
            artifact(AgileArtifactType.EPIC, 1),
            review_state=AgileReviewState.ACCEPTED,
            provenance=ContentProvenance.PRODUCT_MANAGER_EDITED,
            revision=2,
        )
        accepted_batch = AgileArtifactBatch(
            batch_id="accepted-batch",
            product_id=1,
            behavior_profile=AgileBehaviorProfile.BALANCED,
            review_state=AgileReviewState.ACCEPTED,
            prompt_version="1.0.0",
            artifacts=(accepted_artifact,),
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
            accepted_at="2026-08-11T10:01:00.000000Z",
            revision=2,
        )
        self.assertEqual(accepted_batch.revision, 2)
        self.assertIs(
            accepted_batch.artifacts[0].provenance,
            ContentProvenance.PRODUCT_MANAGER_EDITED,
        )
        with self.assertRaises(AgileContractError):
            replace(accepted_batch, accepted_at=None)
        with self.assertRaises(AgileContractError):
            replace(
                accepted_batch,
                review_state=AgileReviewState.PENDING_REVIEW,
            )
        with self.assertRaises(AgileContractError):
            replace(
                accepted_batch,
                updated_at="2026-08-11T09:59:00.000000Z",
            )


if __name__ == "__main__":
    unittest.main()
