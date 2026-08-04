"""Tests for the Phase 9 Checkpoint 1 OpenAI service boundary."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.ai_service import (
    DEFAULT_OPENAI_MODEL,
    AIConfigurationError,
    OpenAIService,
    get_ai_configuration,
)


class AIConfigurationTests(unittest.TestCase):
    def test_missing_api_key_is_user_friendly_and_inactive(self):
        configuration = get_ai_configuration({})

        self.assertFalse(configuration.configured)
        self.assertEqual(configuration.model, DEFAULT_OPENAI_MODEL)
        self.assertIn("optional", configuration.status_message)
        self.assertIn("OPENAI_API_KEY", configuration.status_message)

        factory = Mock()
        with self.assertRaisesRegex(AIConfigurationError, "currently inactive"):
            OpenAIService.from_environment(environ={}, client_factory=factory)
        factory.assert_not_called()

    def test_configured_status_does_not_retain_or_expose_key(self):
        secret = "configured-for-test-only"
        configuration = get_ai_configuration(
            {
                "OPENAI_API_KEY": secret,
                "OPENAI_MODEL": "model-selected-for-test",
            }
        )

        self.assertTrue(configuration.configured)
        self.assertEqual(configuration.model, "model-selected-for-test")
        self.assertNotIn(secret, repr(configuration))
        self.assertNotIn(secret, configuration.status_message)
        self.assertNotIn("api_key", configuration.__dict__)


class OpenAIServiceTests(unittest.TestCase):
    def test_injected_client_uses_responses_api_without_network(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="Mocked response text."
        )
        service = OpenAIService(client, "model-selected-for-test")

        result = service.create_text_response(
            "  Summarize the approved source.  ",
            instructions="  Cite the source section.  ",
        )

        self.assertEqual(result, "Mocked response text.")
        client.responses.create.assert_called_once_with(
            model="model-selected-for-test",
            input="Summarize the approved source.",
            instructions="Cite the source section.",
        )

    def test_environment_factory_is_injected_without_constructing_real_client(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="Factory-backed mock response."
        )
        factory = Mock(return_value=client)

        service = OpenAIService.from_environment(
            environ={"OPENAI_API_KEY": "configured-for-test-only"},
            client_factory=factory,
        )

        factory.assert_called_once_with()
        self.assertEqual(service.model, DEFAULT_OPENAI_MODEL)
        self.assertEqual(
            service.create_text_response("Test the injected factory."),
            "Factory-backed mock response.",
        )


if __name__ == "__main__":
    unittest.main()
