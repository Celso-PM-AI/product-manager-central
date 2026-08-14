"""Core product data structures and field definitions."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from src.agile import AgileArtifactType


class ProductStatus(str, Enum):
    """Approved lifecycle statuses for a product."""

    IDEA = "idea"
    DISCOVERY = "discovery"
    PLANNING = "planning"
    IN_DEVELOPMENT = "in_development"
    LAUNCHED = "launched"
    ARCHIVED = "archived"


class DocumentType(str, Enum):
    """Supported deterministic product-document templates."""

    BRD = "BRD"
    PRD = "PRD"


class DocumentStatus(str, Enum):
    """Approval states for a saved product document."""

    DRAFT = "draft"
    APPROVED = "approved"


class SuccessMatrixStatus(str, Enum):
    """Product-Manager-visible lifecycle status for one PRD outcome."""

    NOT_STARTED = "not_started"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    MET = "met"
    NOT_MET = "not_met"


DEFAULT_PRODUCT_STATUS: Final[ProductStatus] = ProductStatus.DISCOVERY

REQUIRED_PRODUCT_FIELDS: Final[tuple[str, ...]] = (
    "name",
    "description",
    "target_users",
    "business_goal",
    "status",
)

OPTIONAL_PRODUCT_FIELDS: Final[tuple[str, ...]] = (
    "customer_problem",
    "product_strategy",
    "notes",
)

SYSTEM_MANAGED_PRODUCT_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "created_at",
    "updated_at",
)

EDITABLE_PRODUCT_FIELDS: Final[tuple[str, ...]] = (
    REQUIRED_PRODUCT_FIELDS + OPTIONAL_PRODUCT_FIELDS
)

LEGACY_TO_CANONICAL_FIELD_MAP: Final[dict[str, str]] = {
    "product_name": "name",
    "product_idea": "description",
    "target_user": "target_users",
    "business_goal": "business_goal",
    "date_created": "created_at",
}

EDITABLE_DOCUMENT_FIELDS: Final[tuple[str, ...]] = (
    "title",
    "version",
    "document_status",
    "sections",
    "success_matrix",
    "agile_hierarchy",
    "contributors",
    "key_dates_milestones",
    "brd_hierarchy",
    "brd_risks",
)

SYSTEM_MANAGED_DOCUMENT_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "created_at",
    "updated_at",
)


@dataclass
class Product:
    """A product record using the canonical MVP field names."""

    name: str
    description: str
    target_users: str
    business_goal: str
    status: ProductStatus
    customer_problem: str | None = None
    product_strategy: str | None = None
    notes: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class ProductDocument:
    """A BRD or PRD associated with one saved product."""

    product_id: int
    document_type: DocumentType
    title: str
    version: str
    document_status: DocumentStatus
    sections: dict[str, str]
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    success_matrix: tuple["SuccessMatrixEntry", ...] = ()
    agile_hierarchy: tuple["PRDAgileArtifact", ...] = ()
    contributors: tuple["DocumentContributor", ...] = ()
    key_dates_milestones: tuple["DocumentMilestone", ...] = ()
    brd_hierarchy: tuple["BRDHierarchyRow", ...] = ()
    brd_risks: tuple["BRDRiskRow", ...] = ()


@dataclass(frozen=True)
class DocumentContributor:
    """One ordered contributor and their document role."""

    entry_id: str
    position: int
    contributor_name: str
    contributor_role: str


@dataclass(frozen=True)
class DocumentMilestone:
    """One ordered PRD date and milestone pair."""

    entry_id: str
    position: int
    date: str
    milestone: str


@dataclass(frozen=True)
class BRDAcceptanceCriterion:
    """One criterion owned by exactly one level in a BRD hierarchy row."""

    criterion_id: str
    position: int
    text: str


@dataclass(frozen=True)
class BRDHierarchyRow:
    """One readable Epic-to-User-Story chain for BRD authoring and preview."""

    row_id: str
    position: int
    epic_id: str
    epic: str
    epic_acceptance_criteria: tuple[BRDAcceptanceCriterion, ...]
    capability_id: str
    capability_parent_id: str
    capability: str
    capability_acceptance_criteria: tuple[BRDAcceptanceCriterion, ...]
    feature_id: str
    feature_parent_id: str
    feature: str
    feature_acceptance_criteria: tuple[BRDAcceptanceCriterion, ...]
    user_story_id: str
    user_story_parent_id: str
    user_story: str
    user_story_acceptance_criteria: tuple[BRDAcceptanceCriterion, ...]


@dataclass(frozen=True)
class BRDRiskRow:
    """One ordered business risk kept linked to its mitigation."""

    entry_id: str
    position: int
    business_risk: str
    mitigation_strategy: str


@dataclass(frozen=True)
class SuccessMatrixEntry:
    """One independently measurable PRD success outcome."""

    entry_id: str
    position: int
    requirement_outcome: str
    metric: str
    baseline: str | None
    target: str
    minimum_acceptance_threshold: str
    measurement_method: str
    data_source: str
    evaluation_period: str
    validation_owner: str
    status: SuccessMatrixStatus | None


@dataclass(frozen=True)
class PRDAcceptanceCriterion:
    """One independently ordered criterion owned by one PRD Agile artifact."""

    criterion_id: str
    position: int
    text: str


@dataclass(frozen=True)
class PRDAgileArtifact:
    """One PRD-authored Agile item using the shared Agile artifact type."""

    artifact_id: str
    artifact_type: "AgileArtifactType"
    position: int
    title: str
    description: str
    parent_artifact_id: str | None
    acceptance_criteria: tuple[PRDAcceptanceCriterion, ...]


@dataclass(frozen=True)
class RetrievableDocumentSection:
    """One approved source section with citation-ready metadata."""

    product_id: int
    product_name: str
    document_id: int
    document_title: str
    document_type: DocumentType
    document_status: DocumentStatus
    section_key: str
    section_title: str
    section_content: str


@dataclass(frozen=True)
class GeneratedArtifactCitation:
    """Stored citation snapshot for one accepted generated artifact."""

    source_number: int
    source_product_id: int
    source_product_name: str
    document_id: int
    document_title: str
    document_type: DocumentType
    section_key: str
    section_title: str


@dataclass(frozen=True)
class GeneratedArtifact:
    """Human-accepted AI content stored separately from source documents."""

    id: int
    acceptance_key: str
    product_id: int
    request: str
    original_content: str
    accepted_content: str
    was_revised: bool
    citations: tuple[GeneratedArtifactCitation, ...]
    created_at: str
    accepted_at: str
