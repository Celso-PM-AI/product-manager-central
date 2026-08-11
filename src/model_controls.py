"""Separated retrieval controls and capability-gated generation settings."""

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Final, Mapping

from src.agile import AgileBehaviorProfile
from src.agile_profiles import get_profile_definition
from src.ai_service import DEFAULT_OPENAI_MODEL


class ControlValidationError(ValueError):
    """Raised before a provider call when controls or capabilities are invalid."""


DEFAULT_RETRIEVAL_TOP_K: Final[int] = 5
MAX_RETRIEVAL_TOP_K: Final[int] = 50
_MODEL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


@dataclass(frozen=True)
class RetrievalControls:
    """Controls only how many approved chunks retrieval returns."""

    top_k: int = DEFAULT_RETRIEVAL_TOP_K

    def __post_init__(self) -> None:
        if (
            isinstance(self.top_k, bool)
            or not isinstance(self.top_k, int)
            or not 1 <= self.top_k <= MAX_RETRIEVAL_TOP_K
        ):
            raise ControlValidationError(
                f"Retrieval Top-K must be between 1 and {MAX_RETRIEVAL_TOP_K}."
            )


@dataclass(frozen=True)
class OptionalGenerationControl:
    """One validated sampling control and its unsupported-model policy."""

    value: float
    required: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ControlValidationError("Generation control values must be numeric.")
        normalized = float(self.value)
        if not math.isfinite(normalized):
            raise ControlValidationError("Generation control values must be finite.")
        if not isinstance(self.required, bool):
            raise ControlValidationError("Generation control requirement must be boolean.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class GenerationControls:
    """Validated model controls; retrieval Top-K intentionally cannot appear here."""

    temperature: OptionalGenerationControl | None = None
    top_p: OptionalGenerationControl | None = None
    structured_output_required: bool = True

    def __post_init__(self) -> None:
        if self.temperature is not None:
            if not isinstance(self.temperature, OptionalGenerationControl):
                raise ControlValidationError("Temperature control is invalid.")
            if not 0.0 <= self.temperature.value <= 2.0:
                raise ControlValidationError("Temperature must be between 0 and 2.")
        if self.top_p is not None:
            if not isinstance(self.top_p, OptionalGenerationControl):
                raise ControlValidationError("Top-P control is invalid.")
            if not 0.0 <= self.top_p.value <= 1.0:
                raise ControlValidationError("Top-P must be between 0 and 1.")
        if not isinstance(self.structured_output_required, bool):
            raise ControlValidationError("Structured-output requirement is invalid.")


@dataclass(frozen=True)
class ModelCapabilities:
    """Explicit provider/model support known by the application."""

    provider: str
    model: str
    supports_structured_output: bool
    supports_temperature: bool
    supports_top_p: bool

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not _MODEL_ID_PATTERN.fullmatch(
            self.provider
        ):
            raise ControlValidationError("Provider identity is invalid.")
        if not isinstance(self.model, str) or not _MODEL_ID_PATTERN.fullmatch(self.model):
            raise ControlValidationError("Model identity is invalid.")
        for value in (
            self.supports_structured_output,
            self.supports_temperature,
            self.supports_top_p,
        ):
            if not isinstance(value, bool):
                raise ControlValidationError("Model capabilities must be explicit booleans.")


@dataclass(frozen=True)
class ProfileControlMapping:
    """Optional provider hints for one profile, never a grounding guarantee."""

    profile: AgileBehaviorProfile
    controls: GenerationControls

    def __post_init__(self) -> None:
        get_profile_definition(self.profile)
        if not isinstance(self.controls, GenerationControls):
            raise ControlValidationError("Profile generation controls are invalid.")


@dataclass(frozen=True)
class ProviderGenerationSettings:
    """Only settings supported by the selected provider/model capability contract."""

    model: str
    use_structured_output: bool
    temperature: float | None = None
    top_p: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not _MODEL_ID_PATTERN.fullmatch(self.model):
            raise ControlValidationError("Provider generation model is invalid.")
        if not isinstance(self.use_structured_output, bool):
            raise ControlValidationError("Structured-output setting is invalid.")
        for name, value, minimum, maximum in (
            ("Temperature", self.temperature, 0.0, 2.0),
            ("Top-P", self.top_p, 0.0, 1.0),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not minimum <= value <= maximum
            ):
                raise ControlValidationError(f"Mapped {name} is invalid.")

    def as_request_parameters(self) -> Mapping[str, object]:
        parameters: dict[str, object] = {}
        if self.temperature is not None:
            parameters["temperature"] = self.temperature
        if self.top_p is not None:
            parameters["top_p"] = self.top_p
        return MappingProxyType(parameters)


PROFILE_CONTROL_MAPPINGS: Final[tuple[ProfileControlMapping, ...]] = (
    ProfileControlMapping(
        AgileBehaviorProfile.STRICTLY_GROUNDED,
        GenerationControls(temperature=OptionalGenerationControl(0.0)),
    ),
    ProfileControlMapping(
        AgileBehaviorProfile.BALANCED,
        GenerationControls(temperature=OptionalGenerationControl(0.2)),
    ),
    ProfileControlMapping(
        AgileBehaviorProfile.EXPLORATORY,
        GenerationControls(
            temperature=OptionalGenerationControl(0.7),
            top_p=OptionalGenerationControl(0.9),
        ),
    ),
)


def validate_profile_control_mappings(
    mappings: tuple[ProfileControlMapping, ...],
) -> tuple[ProfileControlMapping, ...]:
    if any(not isinstance(item, ProfileControlMapping) for item in mappings):
        raise ControlValidationError("Every profile needs validated generation controls.")
    profiles = [item.profile for item in mappings]
    if len(profiles) != len(set(profiles)) or set(profiles) != set(AgileBehaviorProfile):
        raise ControlValidationError("Every profile must have exactly one control mapping.")
    return mappings


validate_profile_control_mappings(PROFILE_CONTROL_MAPPINGS)


# Official OpenAI documentation confirms Structured Outputs for this model. It
# does not establish Temperature or Top-P support, so those remain disabled.
DEFAULT_MODEL_CAPABILITIES: Final[ModelCapabilities] = ModelCapabilities(
    provider="openai",
    model=DEFAULT_OPENAI_MODEL,
    supports_structured_output=True,
    supports_temperature=False,
    supports_top_p=False,
)


def _supported_optional_control(
    name: str,
    control: OptionalGenerationControl | None,
    *,
    supported: bool,
) -> float | None:
    if control is None:
        return None
    if supported:
        return control.value
    if control.required:
        raise ControlValidationError(
            f"The selected model does not support required {name}."
        )
    return None


def map_profile_generation_settings(
    profile: object,
    capabilities: ModelCapabilities,
    *,
    mappings: tuple[ProfileControlMapping, ...] = PROFILE_CONTROL_MAPPINGS,
) -> ProviderGenerationSettings:
    """Map business behavior to supported hints without substituting controls."""

    definition = get_profile_definition(profile)
    if not isinstance(capabilities, ModelCapabilities):
        raise ControlValidationError("A validated model capability contract is required.")
    validated_mappings = validate_profile_control_mappings(mappings)
    controls = next(
        item.controls
        for item in validated_mappings
        if item.profile is definition.profile
    )
    if controls.structured_output_required and not capabilities.supports_structured_output:
        raise ControlValidationError(
            "The selected model does not support required structured output."
        )
    temperature = _supported_optional_control(
        "Temperature",
        controls.temperature,
        supported=capabilities.supports_temperature,
    )
    top_p = _supported_optional_control(
        "Top-P",
        controls.top_p,
        supported=capabilities.supports_top_p,
    )
    return ProviderGenerationSettings(
        model=capabilities.model,
        use_structured_output=controls.structured_output_required,
        temperature=temperature,
        top_p=top_p,
    )
