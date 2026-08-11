"""Typed contracts for governed Agile artifacts and their provenance."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Final

from src.models import DocumentType


class AgileContractError(ValueError):
    """Raised when an Agile domain contract is malformed."""


class AgileArtifactType(str, Enum):
    """Supported artifacts in hierarchy order."""

    EPIC = "epic"
    CAPABILITY = "capability"
    FEATURE = "feature"
    USER_STORY = "user_story"


class AgileReviewState(str, Enum):
    """Review lifecycle states represented by the domain contract."""

    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AgileBehaviorProfile(str, Enum):
    """Supported behavior-profile identities shared across Agile contracts."""

    STRICTLY_GROUNDED = "strictly_grounded"
    BALANCED = "balanced"
    EXPLORATORY = "exploratory"


class ContentProvenance(str, Enum):
    """Whether accepted content is unchanged AI output or PM-edited."""

    AI_GENERATED = "ai_generated"
    PRODUCT_MANAGER_EDITED = "product_manager_edited"


PARENT_TYPE: Final[dict[AgileArtifactType, AgileArtifactType | None]] = {
    AgileArtifactType.EPIC: None,
    AgileArtifactType.CAPABILITY: AgileArtifactType.EPIC,
    AgileArtifactType.FEATURE: AgileArtifactType.CAPABILITY,
    AgileArtifactType.USER_STORY: AgileArtifactType.FEATURE,
}

_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _require_stable_id(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise AgileContractError(
            f"{field_name} must be a stable 1-to-128 character identifier."
        )
    return value


def _require_text(
    value: object,
    field_name: str,
    maximum: int,
) -> str:
    if not isinstance(value, str):
        raise AgileContractError(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise AgileContractError(
            f"{field_name} must contain 1 to {maximum:,} characters."
        )
    return normalized


def _require_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AgileContractError(f"{field_name} must be a positive integer.")
    return value


def _parse_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AgileContractError(f"{field_name} must be an ISO-8601 UTC timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AgileContractError(
            f"{field_name} must be an ISO-8601 UTC timestamp."
        ) from error
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise AgileContractError(f"{field_name} must be an ISO-8601 UTC timestamp.")
    return parsed


@dataclass(frozen=True)
class AgileSourceReference:
    """Immutable source metadata to snapshot at acceptance time."""

    reference_id: str
    product_id: int
    product_name: str
    document_id: int
    document_title: str
    document_type: DocumentType
    section_key: str
    section_title: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reference_id", _require_stable_id(self.reference_id, "reference_id")
        )
        _require_positive_integer(self.product_id, "product_id")
        object.__setattr__(
            self, "product_name", _require_text(self.product_name, "product_name", 120)
        )
        _require_positive_integer(self.document_id, "document_id")
        object.__setattr__(
            self,
            "document_title",
            _require_text(self.document_title, "document_title", 200),
        )
        if not isinstance(self.document_type, DocumentType):
            raise AgileContractError("document_type must be BRD or PRD.")
        object.__setattr__(
            self, "section_key", _require_text(self.section_key, "section_key", 100)
        )
        object.__setattr__(
            self,
            "section_title",
            _require_text(self.section_title, "section_title", 200),
        )


def _normalize_sources(
    sources: tuple[AgileSourceReference, ...],
    field_name: str,
) -> tuple[AgileSourceReference, ...]:
    normalized = tuple(sources)
    if not normalized:
        raise AgileContractError(f"{field_name} must contain at least one source.")
    if any(not isinstance(source, AgileSourceReference) for source in normalized):
        raise AgileContractError(f"{field_name} contains an invalid source.")
    reference_ids = [source.reference_id for source in normalized]
    if len(reference_ids) != len(set(reference_ids)):
        raise AgileContractError(f"{field_name} contains duplicate source references.")
    return tuple(sorted(normalized, key=lambda source: source.reference_id))


@dataclass(frozen=True)
class AgileAcceptanceCriterion:
    """One ordered, traceable criterion associated with an Agile artifact."""

    criterion_id: str
    position: int
    text: str
    source_references: tuple[AgileSourceReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "criterion_id",
            _require_stable_id(self.criterion_id, "criterion_id"),
        )
        _require_positive_integer(self.position, "criterion position")
        object.__setattr__(self, "text", _require_text(self.text, "criterion text", 2_000))
        object.__setattr__(
            self,
            "source_references",
            _normalize_sources(self.source_references, "criterion source_references"),
        )


@dataclass(frozen=True)
class AgileArtifact:
    """One typed Agile artifact with structured criteria and traceability."""

    artifact_id: str
    artifact_type: AgileArtifactType
    product_id: int
    title: str
    description: str
    acceptance_criteria: tuple[AgileAcceptanceCriterion, ...]
    source_references: tuple[AgileSourceReference, ...]
    position: int
    created_at: str
    updated_at: str
    parent_artifact_id: str | None = None
    review_state: AgileReviewState = AgileReviewState.PENDING_REVIEW
    provenance: ContentProvenance = ContentProvenance.AI_GENERATED
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_id", _require_stable_id(self.artifact_id, "artifact_id")
        )
        if not isinstance(self.artifact_type, AgileArtifactType):
            raise AgileContractError("artifact_type is invalid.")
        _require_positive_integer(self.product_id, "product_id")
        object.__setattr__(self, "title", _require_text(self.title, "title", 200))
        object.__setattr__(
            self, "description", _require_text(self.description, "description", 10_000)
        )
        _require_positive_integer(self.position, "artifact position")
        _require_positive_integer(self.revision, "revision")
        if self.parent_artifact_id is not None:
            object.__setattr__(
                self,
                "parent_artifact_id",
                _require_stable_id(self.parent_artifact_id, "parent_artifact_id"),
            )
            if self.artifact_type is AgileArtifactType.EPIC:
                raise AgileContractError("An Epic cannot have a parent artifact.")
        if not isinstance(self.review_state, AgileReviewState):
            raise AgileContractError("review_state is invalid.")
        if not isinstance(self.provenance, ContentProvenance):
            raise AgileContractError("provenance is invalid.")

        created = _parse_timestamp(self.created_at, "created_at")
        updated = _parse_timestamp(self.updated_at, "updated_at")
        if updated < created:
            raise AgileContractError("updated_at cannot precede created_at.")

        criteria = tuple(self.acceptance_criteria)
        if not criteria:
            raise AgileContractError(
                "Every Agile artifact requires at least one acceptance criterion."
            )
        if any(not isinstance(item, AgileAcceptanceCriterion) for item in criteria):
            raise AgileContractError("acceptance_criteria contains an invalid record.")
        criterion_ids = [item.criterion_id for item in criteria]
        positions = [item.position for item in criteria]
        criterion_texts = [item.text.casefold() for item in criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise AgileContractError("Acceptance criterion IDs must be unique.")
        if len(criterion_texts) != len(set(criterion_texts)):
            raise AgileContractError("Acceptance criterion text must not be duplicated.")
        if positions != list(range(1, len(criteria) + 1)):
            raise AgileContractError(
                "Acceptance criteria must be ordered contiguously from position 1."
            )
        object.__setattr__(self, "acceptance_criteria", criteria)
        object.__setattr__(
            self,
            "source_references",
            _normalize_sources(self.source_references, "artifact source_references"),
        )


@dataclass(frozen=True)
class AgileArtifactBatch:
    """A generation/review batch containing related typed artifacts."""

    batch_id: str
    product_id: int
    behavior_profile: AgileBehaviorProfile
    review_state: AgileReviewState
    prompt_version: str
    artifacts: tuple[AgileArtifact, ...]
    created_at: str
    updated_at: str
    revision: int = 1
    accepted_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_id", _require_stable_id(self.batch_id, "batch_id"))
        _require_positive_integer(self.product_id, "product_id")
        if not isinstance(self.behavior_profile, AgileBehaviorProfile):
            raise AgileContractError("behavior_profile is invalid.")
        if not isinstance(self.review_state, AgileReviewState):
            raise AgileContractError("review_state is invalid.")
        object.__setattr__(
            self,
            "prompt_version",
            _require_text(self.prompt_version, "prompt_version", 50),
        )
        _require_positive_integer(self.revision, "revision")
        created = _parse_timestamp(self.created_at, "created_at")
        updated = _parse_timestamp(self.updated_at, "updated_at")
        if updated < created:
            raise AgileContractError("updated_at cannot precede created_at.")
        if self.review_state is AgileReviewState.ACCEPTED:
            if self.accepted_at is None:
                raise AgileContractError("accepted_at is required for an accepted batch.")
            accepted = _parse_timestamp(self.accepted_at, "accepted_at")
            if accepted < created:
                raise AgileContractError("accepted_at cannot precede created_at.")
        elif self.accepted_at is not None:
            raise AgileContractError("Only an accepted batch can have accepted_at.")

        artifacts = tuple(self.artifacts)
        if not artifacts:
            raise AgileContractError("A batch must contain at least one Agile artifact.")
        if any(not isinstance(item, AgileArtifact) for item in artifacts):
            raise AgileContractError("artifacts contains an invalid record.")
        object.__setattr__(self, "artifacts", artifacts)
        validate_artifact_hierarchy(artifacts, product_id=self.product_id)


def validate_artifact_hierarchy(
    artifacts: tuple[AgileArtifact, ...],
    *,
    product_id: int,
) -> None:
    """Reject duplicate, cross-product, or out-of-order parent relationships."""

    by_id: dict[str, AgileArtifact] = {}
    positions: set[int] = set()
    criterion_ids: set[str] = set()
    for artifact in artifacts:
        if artifact.artifact_id in by_id:
            raise AgileContractError("Artifact IDs must be unique within a batch.")
        if artifact.position in positions:
            raise AgileContractError("Artifact positions must be unique within a batch.")
        if artifact.product_id != product_id:
            raise AgileContractError("Every artifact must belong to the batch product.")
        for source in artifact.source_references:
            if source.product_id != product_id:
                raise AgileContractError("Artifact sources must belong to the batch product.")
        for criterion in artifact.acceptance_criteria:
            if criterion.criterion_id in criterion_ids:
                raise AgileContractError("Criterion IDs must be unique within a batch.")
            criterion_ids.add(criterion.criterion_id)
            for source in criterion.source_references:
                if source.product_id != product_id:
                    raise AgileContractError(
                        "Acceptance-criterion sources must belong to the batch product."
                    )
        by_id[artifact.artifact_id] = artifact
        positions.add(artifact.position)

    if sorted(positions) != list(range(1, len(artifacts) + 1)):
        raise AgileContractError(
            "Artifacts must be ordered contiguously from position 1."
        )
    for artifact in artifacts:
        if artifact.parent_artifact_id is None:
            continue
        parent = by_id.get(artifact.parent_artifact_id)
        if parent is None:
            raise AgileContractError("A parent artifact must exist in the same batch.")
        expected_parent_type = PARENT_TYPE[artifact.artifact_type]
        if parent.artifact_type is not expected_parent_type:
            raise AgileContractError(
                f"{artifact.artifact_type.value} requires a "
                f"{expected_parent_type.value} parent."
            )
        if parent.position >= artifact.position:
            raise AgileContractError("A parent artifact must precede its child.")
