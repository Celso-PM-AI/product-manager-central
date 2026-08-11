"""Immutable behavior-profile definitions for governed Agile generation."""

from dataclasses import asdict, dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping

from src.agile import AgileBehaviorProfile


class AgileProfileError(ValueError):
    """Raised when an Agile behavior-profile selection is invalid."""


class GroundingStrictness(str, Enum):
    EXPLICIT_SOURCE_ONLY = "explicit_source_only"
    REQUIREMENT_PRESERVING = "requirement_preserving"
    LABELED_EXPLORATION = "labeled_exploration"


class CreativityLevel(str, Enum):
    NONE = "none"
    CONSERVATIVE = "conservative"
    EXPLORATORY = "exploratory"


class MissingInformationPolicy(str, Enum):
    REPORT_GAP = "report_gap"
    REPORT_GAP_AND_QUESTION = "report_gap_and_question"
    LABEL_PROPOSAL_OR_QUESTION = "label_proposal_or_question"


class UnsupportedClaimPolicy(str, Enum):
    OMIT_AND_REPORT = "omit_and_report"
    DO_NOT_FILL_GAP = "do_not_fill_gap"
    LABEL_NON_SAVEABLE_PROPOSAL = "label_non_saveable_proposal"


class CitationPolicy(str, Enum):
    ARTIFACT_CRITERION_AND_CLAIM = "artifact_criterion_and_claim"


class InferencePolicy(str, Enum):
    FORBIDDEN = "forbidden"
    REQUIREMENT_PRESERVING_ONLY = "requirement_preserving_only"
    LABELED_UNSUPPORTED_ONLY = "labeled_unsupported_only"


@dataclass(frozen=True)
class AgileProfileDefinition:
    """One code-controlled business behavior profile."""

    profile: AgileBehaviorProfile
    display_name: str
    description: str
    grounding_strictness: GroundingStrictness
    creativity: CreativityLevel
    missing_information: MissingInformationPolicy
    unsupported_claims: UnsupportedClaimPolicy
    citations: CitationPolicy
    assumptions_permitted: bool
    inference_policy: InferencePolicy
    trusted_instructions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile, AgileBehaviorProfile):
            raise AgileProfileError("A supported Agile profile identity is required.")
        enum_fields = (
            (self.grounding_strictness, GroundingStrictness),
            (self.creativity, CreativityLevel),
            (self.missing_information, MissingInformationPolicy),
            (self.unsupported_claims, UnsupportedClaimPolicy),
            (self.citations, CitationPolicy),
            (self.inference_policy, InferencePolicy),
        )
        if any(not isinstance(value, enum_type) for value, enum_type in enum_fields):
            raise AgileProfileError("Profile behavior must use validated policies.")
        if not isinstance(self.assumptions_permitted, bool):
            raise AgileProfileError("Assumption policy must be explicit.")
        if not self.display_name.strip() or not self.description.strip():
            raise AgileProfileError("Profile public metadata cannot be blank.")
        instructions = tuple(instruction.strip() for instruction in self.trusted_instructions)
        if not instructions or any(not instruction for instruction in instructions):
            raise AgileProfileError("Profile instructions cannot be blank.")
        object.__setattr__(self, "trusted_instructions", instructions)


DEFAULT_AGILE_PROFILE: Final[AgileBehaviorProfile] = (
    AgileBehaviorProfile.STRICTLY_GROUNDED
)


AGILE_PROFILE_DEFINITIONS: Final[tuple[AgileProfileDefinition, ...]] = (
    AgileProfileDefinition(
        profile=AgileBehaviorProfile.STRICTLY_GROUNDED,
        display_name="Strictly Grounded",
        description=(
            "Restate, decompose, and format only requirements explicit in the "
            "selected Approved sources."
        ),
        grounding_strictness=GroundingStrictness.EXPLICIT_SOURCE_ONLY,
        creativity=CreativityLevel.NONE,
        missing_information=MissingInformationPolicy.REPORT_GAP,
        unsupported_claims=UnsupportedClaimPolicy.OMIT_AND_REPORT,
        citations=CitationPolicy.ARTIFACT_CRITERION_AND_CLAIM,
        assumptions_permitted=False,
        inference_policy=InferencePolicy.FORBIDDEN,
        trusted_instructions=(
            "Use only explicit requirements in the selected Approved source data.",
            "Do not invent facts, requirements, relationships, or acceptance conditions.",
            "Omit unsupported content and report the missing source information.",
        ),
    ),
    AgileProfileDefinition(
        profile=AgileBehaviorProfile.BALANCED,
        display_name="Balanced",
        description=(
            "Allow conservative requirement-preserving organization while reporting "
            "rather than filling source gaps."
        ),
        grounding_strictness=GroundingStrictness.REQUIREMENT_PRESERVING,
        creativity=CreativityLevel.CONSERVATIVE,
        missing_information=MissingInformationPolicy.REPORT_GAP_AND_QUESTION,
        unsupported_claims=UnsupportedClaimPolicy.DO_NOT_FILL_GAP,
        citations=CitationPolicy.ARTIFACT_CRITERION_AND_CLAIM,
        assumptions_permitted=False,
        inference_policy=InferencePolicy.REQUIREMENT_PRESERVING_ONLY,
        trusted_instructions=(
            "Preserve the meaning and scope of the selected Approved requirements.",
            "Conservative organization is allowed; new requirements and assumptions are not.",
            "Report each source gap explicitly and do not fill it with inferred facts.",
        ),
    ),
    AgileProfileDefinition(
        profile=AgileBehaviorProfile.EXPLORATORY,
        display_name="Exploratory",
        description=(
            "Expose clearly labeled hypotheses, alternatives, or questions separately "
            "from grounded artifacts."
        ),
        grounding_strictness=GroundingStrictness.LABELED_EXPLORATION,
        creativity=CreativityLevel.EXPLORATORY,
        missing_information=MissingInformationPolicy.LABEL_PROPOSAL_OR_QUESTION,
        unsupported_claims=UnsupportedClaimPolicy.LABEL_NON_SAVEABLE_PROPOSAL,
        citations=CitationPolicy.ARTIFACT_CRITERION_AND_CLAIM,
        assumptions_permitted=True,
        inference_policy=InferencePolicy.LABELED_UNSUPPORTED_ONLY,
        trusted_instructions=(
            "Keep grounded artifacts limited to supported Approved source content.",
            "Place hypotheses, alternatives, and assumptions only in labeled proposals.",
            "Mark proposals as unsupported and non-saveable pending approved source evidence.",
        ),
    ),
)


def validate_profile_catalog(
    definitions: tuple[AgileProfileDefinition, ...],
) -> tuple[AgileProfileDefinition, ...]:
    """Validate complete, unique coverage of the Checkpoint 7 identities."""

    if any(not isinstance(item, AgileProfileDefinition) for item in definitions):
        raise AgileProfileError("Every profile must use a validated definition.")
    identities = [item.profile for item in definitions]
    if len(identities) != len(set(identities)):
        raise AgileProfileError("Agile profile identities must be unique.")
    if set(identities) != set(AgileBehaviorProfile):
        raise AgileProfileError("Every approved Agile profile must be defined exactly once.")
    return definitions


validate_profile_catalog(AGILE_PROFILE_DEFINITIONS)
_PROFILES_BY_ID: Final[Mapping[AgileBehaviorProfile, AgileProfileDefinition]] = (
    MappingProxyType({definition.profile: definition for definition in AGILE_PROFILE_DEFINITIONS})
)


def normalize_profile(profile: object) -> AgileBehaviorProfile:
    """Strictly validate a profile identity for trusted execution boundaries."""

    try:
        return (
            profile
            if isinstance(profile, AgileBehaviorProfile)
            else AgileBehaviorProfile(profile)
        )
    except (TypeError, ValueError) as error:
        raise AgileProfileError("Select an approved Agile behavior profile.") from error


def default_profile_selection(profile: object = None) -> AgileBehaviorProfile:
    """Fail closed to Strictly Grounded for missing or invalid UI/session input."""

    try:
        return normalize_profile(profile)
    except AgileProfileError:
        return DEFAULT_AGILE_PROFILE


def get_profile_definition(profile: object) -> AgileProfileDefinition:
    """Return an approved immutable profile or reject unknown input."""

    return _PROFILES_BY_ID[normalize_profile(profile)]


def serialize_profile(profile: object) -> Mapping[str, object]:
    """Return deterministic non-secret metadata for review-batch provenance."""

    definition = get_profile_definition(profile)
    serialized = asdict(definition)
    serialized["profile"] = definition.profile.value
    for field_name in (
        "grounding_strictness",
        "creativity",
        "missing_information",
        "unsupported_claims",
        "citations",
        "inference_policy",
    ):
        serialized[field_name] = getattr(definition, field_name).value
    serialized["trusted_instructions"] = definition.trusted_instructions
    return MappingProxyType(serialized)
