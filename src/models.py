"""Core product data structures and field definitions."""

from dataclasses import dataclass
from enum import Enum
from typing import Final


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
