"""Secure configuration and testable OpenAI Responses API boundary."""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


OPENAI_API_KEY_VARIABLE = "OPENAI_API_KEY"
OPENAI_MODEL_VARIABLE = "OPENAI_MODEL"
DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"


class AIConfigurationError(RuntimeError):
    """Raised when the optional AI capability is not configured."""


class AIServiceError(RuntimeError):
    """Raised when an AI response cannot be safely returned."""


@dataclass(frozen=True)
class AIConfiguration:
    """Non-secret AI status safe to display or log."""

    configured: bool
    model: str
    status_message: str


class ResponsesResource(Protocol):
    """Small part of the official client used by this checkpoint."""

    def create(self, **kwargs: object) -> object:
        """Create one response."""


class OpenAIClient(Protocol):
    """Injectable client contract used by OpenAIService."""

    responses: ResponsesResource


def get_ai_configuration(
    environ: Mapping[str, str] | None = None,
) -> AIConfiguration:
    """Report AI readiness without retaining or returning the API key."""

    source = os.environ if environ is None else environ
    configured = bool(source.get(OPENAI_API_KEY_VARIABLE, "").strip())
    model = source.get(OPENAI_MODEL_VARIABLE, "").strip() or DEFAULT_OPENAI_MODEL
    if configured:
        message = "AI is configured and ready for a future assistant workflow."
    else:
        message = (
            "AI is optional and currently inactive. Set OPENAI_API_KEY in your "
            "environment to activate it."
        )
    return AIConfiguration(
        configured=configured,
        model=model,
        status_message=message,
    )


def _create_official_client() -> OpenAIClient:
    """Create the official SDK client, which reads OPENAI_API_KEY itself."""

    from openai import OpenAI

    return OpenAI()


class OpenAIService:
    """Minimal Responses API adapter; no question-answer workflow lives here."""

    def __init__(self, client: OpenAIClient, model: str) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("An OpenAI model must be configured.")
        self._client = client
        self.model = normalized_model

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        client_factory: Callable[[], OpenAIClient] | None = None,
    ) -> "OpenAIService":
        """Build the service only when the environment contains an API key."""

        configuration = get_ai_configuration(environ)
        if not configuration.configured:
            raise AIConfigurationError(configuration.status_message)
        factory = client_factory or _create_official_client
        return cls(factory(), configuration.model)

    def create_text_response(
        self,
        input_text: str,
        *,
        instructions: str | None = None,
    ) -> str:
        """Call the current Responses API through the injected client."""

        normalized_input = input_text.strip()
        if not normalized_input:
            raise ValueError("Response input cannot be empty.")

        request: dict[str, object] = {
            "model": self.model,
            "input": normalized_input,
        }
        if instructions is not None and instructions.strip():
            request["instructions"] = instructions.strip()

        response = self._client.responses.create(**request)
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIServiceError("OpenAI returned no text response. Please try again.")
        return output_text
