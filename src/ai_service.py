"""Secure configuration and testable OpenAI Responses API boundary."""

import os
import json
from dataclasses import asdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


OPENAI_API_KEY_VARIABLE = "OPENAI_API_KEY"
OPENAI_MODEL_VARIABLE = "OPENAI_MODEL"
OPENAI_EMBEDDING_MODEL_VARIABLE = "OPENAI_EMBEDDING_MODEL"
DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class AIConfigurationError(RuntimeError):
    """Raised when the optional AI capability is not configured."""


class AIServiceError(RuntimeError):
    """Raised when an AI response cannot be safely returned."""


@dataclass(frozen=True)
class AIConfiguration:
    """Non-secret AI status safe to display or log."""

    configured: bool
    model: str
    embedding_model: str
    status_message: str


class ResponsesResource(Protocol):
    """Small part of the official client used by this checkpoint."""

    def create(self, **kwargs: object) -> object:
        """Create one response."""


class EmbeddingsResource(Protocol):
    """Small part of the official client used for embeddings."""

    def create(self, **kwargs: object) -> object:
        """Create embeddings for one ordered input batch."""


class OpenAIClient(Protocol):
    """Injectable client contract used by OpenAIService."""

    responses: ResponsesResource
    embeddings: EmbeddingsResource


def get_ai_configuration(
    environ: Mapping[str, str] | None = None,
) -> AIConfiguration:
    """Report AI readiness without retaining or returning the API key."""

    source = os.environ if environ is None else environ
    configured = bool(source.get(OPENAI_API_KEY_VARIABLE, "").strip())
    model = source.get(OPENAI_MODEL_VARIABLE, "").strip() or DEFAULT_OPENAI_MODEL
    embedding_model = (
        source.get(OPENAI_EMBEDDING_MODEL_VARIABLE, "").strip()
        or DEFAULT_OPENAI_EMBEDDING_MODEL
    )
    if configured:
        message = "AI is configured and ready for grounded draft generation."
    else:
        message = (
            "AI is optional and currently inactive. Set OPENAI_API_KEY in your "
            "environment to activate it."
        )
    return AIConfiguration(
        configured=configured,
        model=model,
        embedding_model=embedding_model,
        status_message=message,
    )


def _create_official_client() -> OpenAIClient:
    """Create the official SDK client, which reads OPENAI_API_KEY itself."""

    from openai import OpenAI

    return OpenAI()


class OpenAIService:
    """Minimal Responses API adapter; no question-answer workflow lives here."""

    def __init__(
        self,
        client: OpenAIClient,
        model: str,
        embedding_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
    ) -> None:
        normalized_model = model.strip()
        normalized_embedding_model = embedding_model.strip()
        if not normalized_model:
            raise ValueError("An OpenAI model must be configured.")
        if not normalized_embedding_model:
            raise ValueError("An OpenAI embedding model must be configured.")
        self._client = client
        self.model = normalized_model
        self.embedding_model = normalized_embedding_model

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
        return cls(
            factory(),
            configuration.model,
            configuration.embedding_model,
        )

    def create_embeddings(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Embed an ordered text batch through the injected official client."""

        if not texts:
            return []
        normalized_texts = [text.strip() for text in texts]
        if any(not text for text in normalized_texts):
            raise ValueError("Embedding input cannot be empty.")

        try:
            response = self._client.embeddings.create(
                model=self.embedding_model,
                input=normalized_texts,
            )
        except Exception as error:
            raise AIServiceError(
                "OpenAI embeddings are temporarily unavailable. Please try again."
            ) from error
        data = getattr(response, "data", None)
        if not isinstance(data, (list, tuple)) or len(data) != len(texts):
            raise AIServiceError("OpenAI returned an invalid embedding response.")

        ordered = sorted(data, key=lambda item: getattr(item, "index", -1))
        if [getattr(item, "index", None) for item in ordered] != list(
            range(len(texts))
        ):
            raise AIServiceError("OpenAI returned an invalid embedding response.")
        vectors: list[tuple[float, ...]] = []
        for item in ordered:
            embedding = getattr(item, "embedding", None)
            if not isinstance(embedding, (list, tuple)) or not embedding:
                raise AIServiceError("OpenAI returned an invalid embedding response.")
            try:
                vectors.append(tuple(float(value) for value in embedding))
            except (TypeError, ValueError) as error:
                raise AIServiceError(
                    "OpenAI returned an invalid embedding response."
                ) from error
        return vectors

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

        try:
            response = self._client.responses.create(**request)
        except Exception as error:
            raise AIServiceError(
                "OpenAI generation is temporarily unavailable. Please try again."
            ) from error
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIServiceError("OpenAI returned no text response. Please try again.")
        return output_text

    def create_structured_response(
        self,
        envelope: object,
        *,
        json_schema: Mapping[str, object],
        settings: object,
    ) -> object:
        """Request strict JSON Schema output for the governed Agile boundary."""

        trusted = getattr(envelope, "trusted_instructions", None)
        application_context = getattr(envelope, "application_context", None)
        request_data = getattr(envelope, "request_data", None)
        source_data = getattr(envelope, "source_data", None)
        model = getattr(settings, "model", None)
        parameters = getattr(settings, "as_request_parameters", None)
        if (
            not isinstance(trusted, tuple)
            or not isinstance(application_context, Mapping)
            or not isinstance(request_data, str)
            or not isinstance(source_data, tuple)
            or not isinstance(model, str)
            or not callable(parameters)
        ):
            raise ValueError("A validated structured Agile request is required.")
        input_data = json.dumps(
            {
                "application_context": dict(application_context),
                "product_manager_request": request_data,
                "untrusted_source_data": [asdict(source) for source in source_data],
            },
            default=lambda value: value.value if hasattr(value, "value") else str(value),
            sort_keys=True,
        )
        request: dict[str, object] = {
            "model": model,
            "instructions": "\n".join(trusted),
            "input": input_data,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "pmc_agile_output",
                    "schema": dict(json_schema),
                    "strict": True,
                }
            },
            **dict(parameters()),
        }
        try:
            response = self._client.responses.create(**request)
        except Exception as error:
            raise AIServiceError(
                "OpenAI structured generation is temporarily unavailable. Please try again."
            ) from error
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise AIServiceError("OpenAI returned no structured response.")
        try:
            return json.loads(output_text)
        except json.JSONDecodeError as error:
            raise AIServiceError("OpenAI returned an invalid structured response.") from error
