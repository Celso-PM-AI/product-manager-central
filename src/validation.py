"""Reusable validation and normalization for editable product data."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from src.models import (
    EDITABLE_DOCUMENT_FIELDS,
    EDITABLE_PRODUCT_FIELDS,
    OPTIONAL_PRODUCT_FIELDS,
    REQUIRED_PRODUCT_FIELDS,
    SYSTEM_MANAGED_DOCUMENT_FIELDS,
    SYSTEM_MANAGED_PRODUCT_FIELDS,
    DocumentStatus,
    DocumentType,
    ProductStatus,
)
from src.document_templates import document_template


NormalizedValue = str | ProductStatus | None

DOCUMENT_TITLE_MAX_LENGTH: Final[int] = 200
DOCUMENT_VERSION_MAX_LENGTH: Final[int] = 50
DOCUMENT_SECTION_MAX_LENGTH: Final[int] = 10_000

TEXT_FIELD_MAX_LENGTHS: Final[dict[str, int]] = {
    "name": 120,
    "description": 2_000,
    "target_users": 1_000,
    "business_goal": 2_000,
    "customer_problem": 2_000,
    "product_strategy": 3_000,
    "notes": 5_000,
}

FIELD_LABELS: Final[dict[str, str]] = {
    "name": "Name",
    "description": "Description",
    "target_users": "Target users",
    "business_goal": "Business goal",
    "status": "Status",
    "customer_problem": "Customer problem",
    "product_strategy": "Product strategy",
    "notes": "Notes",
    "id": "ID",
    "created_at": "Created at",
    "updated_at": "Updated at",
}

REQUIRED_TEXT_FIELDS: Final[tuple[str, ...]] = tuple(
    field for field in REQUIRED_PRODUCT_FIELDS if field != "status"
)


@dataclass
class ValidationResult:
    """The normalized values and all errors from one validation pass.

    A valid status is always returned as a ``ProductStatus`` enum member,
    whether the supplied value was a lowercase string or an enum member.
    Because ``ProductStatus`` inherits from ``str``, the normalized value
    remains compatible with the approved lowercase stored strings.
    """

    normalized_data: dict[str, NormalizedValue]
    errors: dict[str, str]

    @property
    def is_valid(self) -> bool:
        """Return True when validation found no errors."""

        return not self.errors


@dataclass
class DocumentValidationResult:
    """Normalized document values and all errors from one validation pass."""

    normalized_data: dict[str, object]
    errors: dict[str, str]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def normalize_text(value: str) -> str:
    """Remove outer whitespace while preserving internal content."""

    return value.strip()


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize blank optional text to None."""

    if value is None:
        return None

    normalized = normalize_text(value)
    return normalized or None


def _required_error(field: str) -> str:
    return f"{FIELD_LABELS[field]} is required."


def _text_type_error(field: str) -> str:
    return f"{FIELD_LABELS[field]} must be text."


def _length_error(field: str) -> str:
    maximum = TEXT_FIELD_MAX_LENGTHS[field]
    return f"{FIELD_LABELS[field]} must be {maximum:,} characters or fewer."


def _status_error() -> str:
    approved = ", ".join(status.value for status in ProductStatus)
    return f"Status must be one of: {approved}."


def validate_product(data: Mapping[str, object]) -> ValidationResult:
    """Validate and normalize canonical editable product input.

    The supplied mapping is copied and never mutated. Every supported field
    is checked in one pass, so the returned result contains all discovered
    errors. Unknown fields and system-managed fields are rejected.
    """

    supplied_data = dict(data)
    normalized_data: dict[str, NormalizedValue] = {}
    errors: dict[str, str] = {}

    for field in REQUIRED_TEXT_FIELDS:
        if field not in supplied_data or supplied_data[field] is None:
            errors[field] = _required_error(field)
            continue

        value = supplied_data[field]
        if not isinstance(value, str):
            errors[field] = _text_type_error(field)
            continue

        normalized = normalize_text(value)
        if not normalized:
            errors[field] = _required_error(field)
            continue

        if len(normalized) > TEXT_FIELD_MAX_LENGTHS[field]:
            errors[field] = _length_error(field)
            continue

        normalized_data[field] = normalized

    if "status" not in supplied_data or supplied_data["status"] is None:
        errors["status"] = _required_error("status")
    else:
        status_value = supplied_data["status"]

        if isinstance(status_value, ProductStatus):
            normalized_data["status"] = status_value
        elif isinstance(status_value, str):
            normalized_status = normalize_text(status_value)
            if not normalized_status:
                errors["status"] = _required_error("status")
            else:
                try:
                    normalized_data["status"] = ProductStatus(normalized_status)
                except ValueError:
                    errors["status"] = _status_error()
        else:
            errors["status"] = _status_error()

    for field in OPTIONAL_PRODUCT_FIELDS:
        if field not in supplied_data or supplied_data[field] is None:
            normalized_data[field] = None
            continue

        value = supplied_data[field]
        if not isinstance(value, str):
            errors[field] = _text_type_error(field)
            continue

        normalized = normalize_optional_text(value)
        if normalized is None:
            normalized_data[field] = None
            continue

        if len(normalized) > TEXT_FIELD_MAX_LENGTHS[field]:
            errors[field] = _length_error(field)
            continue

        normalized_data[field] = normalized

    for field in SYSTEM_MANAGED_PRODUCT_FIELDS:
        if field in supplied_data:
            label = FIELD_LABELS[field]
            errors[field] = f"{label} is system-managed and cannot be supplied."

    known_fields = set(EDITABLE_PRODUCT_FIELDS) | set(SYSTEM_MANAGED_PRODUCT_FIELDS)
    for field in supplied_data:
        if field not in known_fields:
            errors[str(field)] = "Unknown field."

    return ValidationResult(
        normalized_data=normalized_data,
        errors=errors,
    )


def _document_enum_value(
    supplied: object,
    enum_type: type[DocumentType] | type[DocumentStatus],
) -> DocumentType | DocumentStatus | None:
    if isinstance(supplied, enum_type):
        return supplied
    if not isinstance(supplied, str):
        return None
    try:
        return enum_type(normalize_text(supplied))
    except ValueError:
        return None


def validate_document(data: Mapping[str, object]) -> DocumentValidationResult:
    """Validate and normalize a complete BRD or PRD input mapping.

    Draft body sections may be blank. Approved documents require nonblank
    content for every stable section in their selected template.
    """

    supplied_data = dict(data)
    normalized_data: dict[str, object] = {}
    errors: dict[str, str] = {}

    product_id = supplied_data.get("product_id")
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id < 1:
        errors["product_id"] = "Associated product ID must be a positive integer."
    else:
        normalized_data["product_id"] = product_id

    document_type = _document_enum_value(
        supplied_data.get("document_type"),
        DocumentType,
    )
    if document_type is None:
        errors["document_type"] = "Document type must be BRD or PRD."
    else:
        normalized_data["document_type"] = document_type

    for field, label, maximum in (
        ("title", "Document title", DOCUMENT_TITLE_MAX_LENGTH),
        ("version", "Version", DOCUMENT_VERSION_MAX_LENGTH),
    ):
        value = supplied_data.get(field)
        if not isinstance(value, str):
            errors[field] = f"{label} is required."
            continue
        normalized = normalize_text(value)
        if not normalized:
            errors[field] = f"{label} is required."
        elif len(normalized) > maximum:
            errors[field] = f"{label} must be {maximum:,} characters or fewer."
        else:
            normalized_data[field] = normalized

    document_status = _document_enum_value(
        supplied_data.get("document_status"),
        DocumentStatus,
    )
    if document_status is None:
        errors["document_status"] = "Document status must be Draft or Approved."
    else:
        normalized_data["document_status"] = document_status

    supplied_sections = supplied_data.get("sections")
    if not isinstance(supplied_sections, Mapping):
        errors["sections"] = "Document sections must be supplied."
    elif document_type is not None:
        definitions = document_template(document_type)
        known_keys = {definition.key for definition in definitions}
        normalized_sections: dict[str, str] = {}
        for definition in definitions:
            value = supplied_sections.get(definition.key, "")
            error_key = f"sections.{definition.key}"
            if not isinstance(value, str):
                errors[error_key] = f"{definition.label} must be text."
                continue
            normalized = normalize_text(value)
            if len(normalized) > DOCUMENT_SECTION_MAX_LENGTH:
                errors[error_key] = (
                    f"{definition.label} must be "
                    f"{DOCUMENT_SECTION_MAX_LENGTH:,} characters or fewer."
                )
                continue
            if document_status is DocumentStatus.APPROVED and not normalized:
                errors[error_key] = (
                    f"{definition.label} is required before approval."
                )
                continue
            normalized_sections[definition.key] = normalized

        for key in supplied_sections:
            if key not in known_keys:
                errors[f"sections.{key}"] = "Unknown document section."
        normalized_data["sections"] = normalized_sections

    for field in SYSTEM_MANAGED_DOCUMENT_FIELDS:
        if field in supplied_data:
            errors[field] = (
                f"{field.replace('_', ' ').title()} is system-managed "
                "and cannot be supplied."
            )

    known_fields = {
        "product_id",
        "document_type",
        *EDITABLE_DOCUMENT_FIELDS,
        *SYSTEM_MANAGED_DOCUMENT_FIELDS,
    }
    for field in supplied_data:
        if field not in known_fields:
            errors[str(field)] = "Unknown field."

    return DocumentValidationResult(normalized_data, errors)
