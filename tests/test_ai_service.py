"""Tests for the Phase 9 Checkpoint 1 OpenAI service boundary."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.ai_service import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    DEFAULT_OPENAI_MODEL,
    AIConfigurationError,
    AIServiceError,
    OpenAIService,
    get_ai_configuration,
)


class AIConfigurationTests(unittest.TestCase):
    def test_missing_api_key_is_user_friendly_and_inactive(self):
        configuration = get_ai_configuration({})

        self.assertFalse(configuration.configured)
        self.assertEqual(configuration.model, DEFAULT_OPENAI_MODEL)
        self.assertEqual(
            configuration.embedding_model,
            DEFAULT_OPENAI_EMBEDDING_MODEL,
        )
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
                "OPENAI_EMBEDDING_MODEL": "embedding-model-for-test",
            }
        )

        self.assertTrue(configuration.configured)
        self.assertEqual(configuration.model, "model-selected-for-test")
        self.assertEqual(
            configuration.embedding_model,
            "embedding-model-for-test",
        )
        self.assertNotIn(secret, repr(configuration))
        self.assertNotIn(secret, configuration.status_message)
        self.assertNotIn("api_key", configuration.__dict__)


class OpenAIServiceTests(unittest.TestCase):
    def test_injected_client_creates_ordered_embeddings_without_network(self):
        client = Mock()
        client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0, 1]),
                SimpleNamespace(index=0, embedding=[1, 0]),
            ]
        )
        service = OpenAIService(
            client,
            "response-model-for-test",
            "embedding-model-for-test",
        )

        vectors = service.create_embeddings([" First ", "Second"])

        self.assertEqual(vectors, [(1.0, 0.0), (0.0, 1.0)])
        client.embeddings.create.assert_called_once_with(
            model="embedding-model-for-test",
            input=["First", "Second"],
        )

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

    def test_mocked_api_failure_is_sanitized(self):
        client = Mock()
        client.responses.create.side_effect = RuntimeError(
            "provider details and credential-like material"
        )
        service = OpenAIService(client, "model-selected-for-test")

        with self.assertRaisesRegex(
            AIServiceError,
            "temporarily unavailable",
        ) as raised:
            service.create_text_response("Draft from approved sources.")

        self.assertNotIn("provider details", str(raised.exception))

    def test_malformed_text_response_is_rejected(self):
        client = Mock()
        for malformed in (None, "", "   ", 42):
            with self.subTest(malformed=malformed):
                client.responses.create.return_value = SimpleNamespace(
                    output_text=malformed
                )
                service = OpenAIService(client, "model-selected-for-test")
                with self.assertRaisesRegex(AIServiceError, "no text response"):
                    service.create_text_response("Draft from approved sources.")


if __name__ == "__main__":
    unittest.main()
