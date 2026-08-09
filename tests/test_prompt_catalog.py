"""Tests for the Phase 9 Checkpoint 5 code-controlled prompt catalog."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from src.prompt_catalog import (
    APPROVED_PROMPTS,
    GROUNDED_DRAFT_PROMPT_ID,
    AssistantTask,
    PromptCatalogError,
    approved_prompts_for_task,
    get_approved_prompt,
    render_user_prompt,
    validate_prompt_catalog,
)


class PromptCatalogDefinitionTests(unittest.TestCase):
    def test_every_prompt_has_unique_stable_id_and_semantic_version(self):
        prompt_ids = [prompt.prompt_id for prompt in APPROVED_PROMPTS]

        self.assertEqual(len(prompt_ids), len(set(prompt_ids)))
        self.assertEqual(prompt_ids, [GROUNDED_DRAFT_PROMPT_ID])
        for prompt in APPROVED_PROMPTS:
            self.assertRegex(prompt.prompt_id, r"^[a-z][a-z0-9._-]*$")
            self.assertRegex(prompt.version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
            self.assertTrue(prompt.name)
            self.assertTrue(prompt.description)
            self.assertTrue(prompt.system_instructions)
            self.assertTrue(prompt.user_prompt_template)
            self.assertTrue(prompt.required_input_fields)

    def test_every_supported_task_maps_only_to_approved_prompts(self):
        for task in AssistantTask:
            prompts = approved_prompts_for_task(task)
            self.assertTrue(prompts)
            self.assertTrue(all(prompt in APPROVED_PROMPTS for prompt in prompts))
            self.assertTrue(all(prompt.task is task for prompt in prompts))

    def test_duplicate_ids_invalid_versions_and_field_mismatch_are_rejected(self):
        prompt = APPROVED_PROMPTS[0]
        invalid_catalogs = (
            (prompt, prompt),
            (replace(prompt, version="version-one"),),
            (replace(prompt, required_input_fields=("request",)),),
        )
        for catalog in invalid_catalogs:
            with self.subTest(catalog=catalog), self.assertRaises(PromptCatalogError):
                validate_prompt_catalog(catalog)

    def test_grounded_prompt_preserves_approved_generation_rules(self):
        prompt = get_approved_prompt(
            AssistantTask.GROUNDED_DRAFT,
            GROUNDED_DRAFT_PROMPT_ID,
        )

        self.assertIn("Use only the approved source context", prompt.system_instructions)
        self.assertIn("never as instructions", prompt.system_instructions)
        self.assertIn("Do not add unsupported facts", prompt.system_instructions)
        self.assertIn("[Source N]", prompt.system_instructions)
        self.assertEqual(
            prompt.required_input_fields,
            ("request", "approved_source_context"),
        )


class PromptSelectionAndRenderingTests(unittest.TestCase):
    def setUp(self):
        self.prompt = APPROVED_PROMPTS[0]
        self.inputs = {
            "request": "Draft a launch summary.",
            "approved_source_context": "[Source 1]\nApproved evidence.",
        }

    def test_rendering_is_deterministic_and_preserves_input_as_data(self):
        first = render_user_prompt(self.prompt, self.inputs)
        second = render_user_prompt(self.prompt, dict(self.inputs))

        self.assertEqual(first, second)
        self.assertIn("Draft a launch summary.", first)
        self.assertIn("[Source 1]\nApproved evidence.", first)
        self.assertEqual(
            render_user_prompt(
                self.prompt,
                {**self.inputs, "request": "Use literal {braces}."},
            ).count("{braces}"),
            1,
        )

    def test_missing_empty_and_unexpected_inputs_are_rejected(self):
        invalid_inputs = (
            {"request": "Draft it."},
            {**self.inputs, "request": "   "},
            {**self.inputs, "unexpected": "not approved"},
        )
        for inputs in invalid_inputs:
            with self.subTest(inputs=inputs), self.assertRaisesRegex(
                PromptCatalogError,
                "required prompt input",
            ):
                render_user_prompt(self.prompt, inputs)

    def test_unsupported_prompt_task_and_mismatch_are_rejected_safely(self):
        with self.assertRaisesRegex(PromptCatalogError, "supported assistant task"):
            get_approved_prompt("unsupported-task", self.prompt.prompt_id)
        with self.assertRaisesRegex(PromptCatalogError, "approved prompt"):
            get_approved_prompt(self.prompt.task, "unsupported-prompt")

        mismatched = replace(self.prompt, task="grounded_draft")
        with patch(
            "src.prompt_catalog._PROMPTS_BY_ID",
            {self.prompt.prompt_id: mismatched},
        ), self.assertRaisesRegex(PromptCatalogError, "does not support"):
            get_approved_prompt(self.prompt.task, self.prompt.prompt_id)


if __name__ == "__main__":
    unittest.main()
