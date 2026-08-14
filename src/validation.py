"""Reusable validation and normalization for editable product data."""

from collections.abc import Mapping, Sequence
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
    SuccessMatrixStatus,
)
from src.document_templates import document_template
from src.agile import AgileArtifactType, PARENT_TYPE, is_stable_identifier


NormalizedValue = str | ProductStatus | None

DOCUMENT_TITLE_MAX_LENGTH: Final[int] = 200
DOCUMENT_VERSION_MAX_LENGTH: Final[int] = 50
DOCUMENT_SECTION_MAX_LENGTH: Final[int] = 10_000
SUCCESS_MATRIX_FIELD_MAX_LENGTH: Final[int] = 2_000
SUCCESS_MATRIX_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "requirement_outcome",
    "metric",
    "target",
    "minimum_acceptance_threshold",
    "measurement_method",
    "data_source",
    "evaluation_period",
    "validation_owner",
    "status",
)
SUCCESS_MATRIX_FIELDS: Final[tuple[str, ...]] = (
    "entry_id",
    "position",
    "requirement_outcome",
    "metric",
    "baseline",
    "target",
    "minimum_acceptance_threshold",
    "measurement_method",
    "data_source",
    "evaluation_period",
    "validation_owner",
    "status",
)
PRD_AGILE_ARTIFACT_FIELDS: Final[tuple[str, ...]] = (
    "artifact_id",
    "artifact_type",
    "position",
    "title",
    "description",
    "parent_artifact_id",
    "acceptance_criteria",
)
PRD_ACCEPTANCE_CRITERION_FIELDS: Final[tuple[str, ...]] = (
    "criterion_id",
    "position",
    "text",
)
CONTRIBUTOR_FIELDS: Final[tuple[str, ...]] = (
    "entry_id", "position", "contributor_name", "contributor_role"
)
MILESTONE_FIELDS: Final[tuple[str, ...]] = (
    "entry_id", "position", "date", "milestone"
)
BRD_RISK_FIELDS: Final[tuple[str, ...]] = (
    "entry_id", "position", "business_risk", "mitigation_strategy"
)
BRD_HIERARCHY_LEVELS: Final[tuple[str, ...]] = (
    "epic", "capability", "feature", "user_story"
)
BRD_HIERARCHY_FIELDS: Final[tuple[str, ...]] = (
    "row_id", "position",
    "epic_id", "epic", "epic_acceptance_criteria",
    "capability_id", "capability_parent_id", "capability", "capability_acceptance_criteria",
    "feature_id", "feature_parent_id", "feature", "feature_acceptance_criteria",
    "user_story_id", "user_story_parent_id", "user_story", "user_story_acceptance_criteria",
)

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


def _validate_success_matrix(
    supplied: object,
    *,
    document_type: DocumentType,
    document_status: DocumentStatus | None,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Normalize ordered PRD outcomes while allowing incomplete Draft rows."""

    errors: dict[str, str] = {}
    if supplied is None:
        supplied = ()
    if isinstance(supplied, (str, bytes)) or not isinstance(supplied, Sequence):
        return [], {"success_matrix": "Success Matrix entries must be supplied as an ordered list."}
    rows = list(supplied)
    if document_type is DocumentType.BRD and rows:
        return [], {"success_matrix": "The Success Matrix is available only for PRDs."}
    if (
        document_type is DocumentType.PRD
        and document_status is DocumentStatus.APPROVED
        and not rows
    ):
        errors["success_matrix"] = (
            "At least one complete Success Matrix entry is required before PRD approval."
        )

    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    text_fields = tuple(
        field
        for field in SUCCESS_MATRIX_FIELDS
        if field not in {"entry_id", "position", "status"}
    )
    for index, supplied_row in enumerate(rows, start=1):
        prefix = f"success_matrix.{index}"
        if not isinstance(supplied_row, Mapping):
            errors[prefix] = "Each Success Matrix entry must be a structured row."
            continue
        row = dict(supplied_row)
        for unknown in set(row) - set(SUCCESS_MATRIX_FIELDS):
            errors[f"{prefix}.{unknown}"] = "Unknown Success Matrix field."

        entry_id = row.get("entry_id")
        if entry_id in (None, ""):
            normalized_id = ""
        elif not isinstance(entry_id, str) or not entry_id.strip():
            errors[f"{prefix}.entry_id"] = "Success Matrix entry ID is invalid."
            normalized_id = ""
        else:
            normalized_id = entry_id.strip()
            if len(normalized_id) > 128:
                errors[f"{prefix}.entry_id"] = "Success Matrix entry ID is too long."
            elif normalized_id in seen_ids:
                errors[f"{prefix}.entry_id"] = "Success Matrix entry IDs must be unique."
            seen_ids.add(normalized_id)

        normalized_row: dict[str, object] = {
            "entry_id": normalized_id,
            "position": index,
        }
        for field in text_fields:
            value = row.get(field, "")
            if value is None and field == "baseline":
                normalized_row[field] = None
                continue
            if not isinstance(value, str):
                errors[f"{prefix}.{field}"] = (
                    f"{field.replace('_', ' ').title()} must be text."
                )
                continue
            value = normalize_text(value)
            if len(value) > SUCCESS_MATRIX_FIELD_MAX_LENGTH:
                errors[f"{prefix}.{field}"] = (
                    f"{field.replace('_', ' ').title()} must be "
                    f"{SUCCESS_MATRIX_FIELD_MAX_LENGTH:,} characters or fewer."
                )
                continue
            if (
                document_status is DocumentStatus.APPROVED
                and field in SUCCESS_MATRIX_REQUIRED_FIELDS
                and not value
            ):
                errors[f"{prefix}.{field}"] = (
                    f"{field.replace('_', ' ').title()} is required before PRD approval."
                )
            normalized_row[field] = value or (None if field == "baseline" else "")

        raw_status = row.get("status", "")
        try:
            status = (
                raw_status
                if isinstance(raw_status, SuccessMatrixStatus)
                else SuccessMatrixStatus(normalize_text(raw_status))
            )
        except (TypeError, ValueError):
            status = None
        if status is None:
            if document_status is DocumentStatus.APPROVED:
                errors[f"{prefix}.status"] = "Status is required before PRD approval."
            normalized_row["status"] = ""
        else:
            normalized_row["status"] = status
        normalized.append(normalized_row)
    return normalized, errors


def _validate_prd_agile_hierarchy(
    supplied: object,
    *,
    document_type: DocumentType,
    document_status: DocumentStatus | None,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Validate PRD authoring records against the shared typed parent map."""

    errors: dict[str, str] = {}
    if supplied is None:
        supplied = ()
    if isinstance(supplied, (str, bytes)) or not isinstance(supplied, Sequence):
        return [], {"agile_hierarchy": "PRD Agile hierarchy entries must be an ordered list."}
    rows = list(supplied)
    if document_type is DocumentType.BRD and rows:
        return [], {"agile_hierarchy": "The Agile hierarchy is available only for PRDs."}

    approved = (
        document_type is DocumentType.PRD
        and document_status is DocumentStatus.APPROVED
    )
    normalized: list[dict[str, object]] = []
    seen_artifact_ids: set[str] = set()
    seen_criterion_ids: set[str] = set()
    type_positions = {artifact_type: 0 for artifact_type in AgileArtifactType}

    for index, supplied_row in enumerate(rows, start=1):
        prefix = f"agile_hierarchy.{index}"
        if not isinstance(supplied_row, Mapping):
            errors[prefix] = "Each Agile hierarchy entry must be structured."
            continue
        row = dict(supplied_row)
        for unknown in set(row) - set(PRD_AGILE_ARTIFACT_FIELDS):
            errors[f"{prefix}.{unknown}"] = "Unknown Agile hierarchy field."

        raw_type = row.get("artifact_type", "")
        try:
            artifact_type = (
                raw_type
                if isinstance(raw_type, AgileArtifactType)
                else AgileArtifactType(normalize_text(raw_type))
            )
        except (TypeError, ValueError):
            errors[f"{prefix}.artifact_type"] = (
                "Artifact type must be Epic, Capability, Feature, or User Story."
            )
            continue
        type_positions[artifact_type] += 1

        raw_id = row.get("artifact_id", "")
        artifact_id = raw_id.strip() if isinstance(raw_id, str) else ""
        if raw_id not in ("", None) and not artifact_id:
            errors[f"{prefix}.artifact_id"] = "Artifact ID is invalid."
        if artifact_id and not is_stable_identifier(artifact_id):
            errors[f"{prefix}.artifact_id"] = (
                "Artifact ID must satisfy the stable Agile identifier contract."
            )
        if artifact_id and artifact_id in seen_artifact_ids:
            errors[f"{prefix}.artifact_id"] = "Artifact IDs must be unique."
        if artifact_id:
            seen_artifact_ids.add(artifact_id)

        title = row.get("title", "")
        description = row.get("description", "")
        for field, value, maximum in (
            ("title", title, 200),
            ("description", description, 10_000),
        ):
            if not isinstance(value, str):
                errors[f"{prefix}.{field}"] = f"{field.title()} must be text."
                value = ""
            value = normalize_text(value)
            if len(value) > maximum:
                errors[f"{prefix}.{field}"] = (
                    f"{field.title()} must be {maximum:,} characters or fewer."
                )
            if approved and not value:
                errors[f"{prefix}.{field}"] = (
                    f"{field.title()} is required before PRD approval."
                )
            if field == "title":
                title = value
            else:
                description = value

        raw_parent = row.get("parent_artifact_id")
        parent_id = (
            raw_parent.strip()
            if isinstance(raw_parent, str) and raw_parent.strip()
            else None
        )
        if parent_id is not None and not is_stable_identifier(parent_id):
            errors[f"{prefix}.parent_artifact_id"] = (
                "Parent artifact ID must satisfy the stable Agile identifier contract."
            )
        if artifact_type is AgileArtifactType.EPIC and parent_id is not None:
            errors[f"{prefix}.parent_artifact_id"] = "An Epic cannot have a parent."
        elif approved and artifact_type is not AgileArtifactType.EPIC and parent_id is None:
            errors[f"{prefix}.parent_artifact_id"] = (
                f"{artifact_type.value.replace('_', ' ').title()} requires a "
                f"{PARENT_TYPE[artifact_type].value.replace('_', ' ').title()} parent."
            )

        raw_criteria = row.get("acceptance_criteria", ())
        if isinstance(raw_criteria, (str, bytes)) or not isinstance(raw_criteria, Sequence):
            errors[f"{prefix}.acceptance_criteria"] = (
                "Acceptance criteria must be an ordered list."
            )
            raw_criteria = ()
        criteria: list[dict[str, object]] = []
        for criterion_index, supplied_criterion in enumerate(raw_criteria, start=1):
            criterion_prefix = f"{prefix}.acceptance_criteria.{criterion_index}"
            if not isinstance(supplied_criterion, Mapping):
                errors[criterion_prefix] = "Each acceptance criterion must be structured."
                continue
            criterion = dict(supplied_criterion)
            for unknown in set(criterion) - set(PRD_ACCEPTANCE_CRITERION_FIELDS):
                errors[f"{criterion_prefix}.{unknown}"] = "Unknown acceptance-criterion field."
            raw_criterion_id = criterion.get("criterion_id", "")
            criterion_id = (
                raw_criterion_id.strip()
                if isinstance(raw_criterion_id, str)
                else ""
            )
            if criterion_id and not is_stable_identifier(criterion_id):
                errors[f"{criterion_prefix}.criterion_id"] = (
                    "Criterion ID must satisfy the stable Agile identifier contract."
                )
            if criterion_id and criterion_id in seen_criterion_ids:
                errors[f"{criterion_prefix}.criterion_id"] = "Criterion IDs must be unique."
            if criterion_id:
                seen_criterion_ids.add(criterion_id)
            text = criterion.get("text", "")
            if not isinstance(text, str):
                errors[f"{criterion_prefix}.text"] = "Criterion text must be text."
                text = ""
            text = normalize_text(text)
            if len(text) > 2_000:
                errors[f"{criterion_prefix}.text"] = (
                    "Criterion text must be 2,000 characters or fewer."
                )
            if approved and not text:
                errors[f"{criterion_prefix}.text"] = (
                    "A measurable criterion is required before PRD approval."
                )
            criteria.append(
                {
                    "criterion_id": criterion_id,
                    "position": criterion_index,
                    "text": text,
                }
            )
        if approved and not criteria:
            errors[f"{prefix}.acceptance_criteria"] = (
                "Every Agile hierarchy entry requires acceptance criteria before PRD approval."
            )
        normalized.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "position": type_positions[artifact_type],
                "title": title,
                "description": description,
                "parent_artifact_id": parent_id,
                "acceptance_criteria": criteria,
            }
        )

    by_id = {
        row["artifact_id"]: row
        for row in normalized
        if row["artifact_id"]
    }
    for index, row in enumerate(normalized, start=1):
        artifact_type = row["artifact_type"]
        parent_id = row["parent_artifact_id"]
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            if approved:
                errors[f"agile_hierarchy.{index}.parent_artifact_id"] = (
                    "The selected parent does not exist in this PRD."
                )
            continue
        if parent["artifact_type"] is not PARENT_TYPE[artifact_type]:
            errors[f"agile_hierarchy.{index}.parent_artifact_id"] = (
                f"{artifact_type.value.replace('_', ' ').title()} must belong to "
                f"a {PARENT_TYPE[artifact_type].value.replace('_', ' ').title()}."
            )

    if approved:
        present_types = {row["artifact_type"] for row in normalized}
        for artifact_type in AgileArtifactType:
            if artifact_type not in present_types:
                errors[f"agile_hierarchy.{artifact_type.value}"] = (
                    f"At least one {artifact_type.value.replace('_', ' ').title()} "
                    "is required before PRD approval."
                )
    return normalized, errors


def _legacy_row_id(prefix: str, position: int = 1) -> str:
    """Return a deterministic valid identifier for legacy initialization."""

    return f"legacy-{prefix}-{position}"


def _structured_rows(
    supplied: object,
    *,
    field: str,
    fields: tuple[str, ...],
    text_fields: tuple[str, ...],
    approved: bool,
    required_label: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Validate simple repeatable rows while allowing incomplete Draft entries."""

    if supplied is None:
        supplied = ()
    if isinstance(supplied, (str, bytes)) or not isinstance(supplied, Sequence):
        return [], {field: f"{required_label} must be supplied as an ordered list."}
    errors: dict[str, str] = {}
    rows = list(supplied)
    if approved and not rows:
        errors[field] = f"At least one complete {required_label} entry is required before approval."
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, supplied_row in enumerate(rows, start=1):
        prefix = f"{field}.{index}"
        if not isinstance(supplied_row, Mapping):
            errors[prefix] = f"Each {required_label} entry must be a structured row."
            continue
        row = dict(supplied_row)
        for unknown in set(row) - set(fields):
            errors[f"{prefix}.{unknown}"] = f"Unknown {required_label} field."
        raw_id = row.get("entry_id", "")
        entry_id = raw_id.strip() if isinstance(raw_id, str) else ""
        if entry_id and (not is_stable_identifier(entry_id) or entry_id in seen_ids):
            errors[f"{prefix}.entry_id"] = f"{required_label.title()} entry ID must be stable and unique."
        if entry_id:
            seen_ids.add(entry_id)
        normalized_row: dict[str, object] = {"entry_id": entry_id, "position": index}
        for text_field in text_fields:
            value = row.get(text_field, "")
            if not isinstance(value, str):
                errors[f"{prefix}.{text_field}"] = f"{text_field.replace('_', ' ').title()} must be text."
                value = ""
            value = normalize_text(value)
            if len(value) > DOCUMENT_SECTION_MAX_LENGTH:
                errors[f"{prefix}.{text_field}"] = f"{text_field.replace('_', ' ').title()} must be {DOCUMENT_SECTION_MAX_LENGTH:,} characters or fewer."
            if approved and not entry_id.startswith("legacy-") and not value:
                errors[f"{prefix}.{text_field}"] = f"{text_field.replace('_', ' ').title()} is required before approval."
            normalized_row[text_field] = value
        normalized.append(normalized_row)
    return normalized, errors


def _validate_brd_hierarchy(
    supplied: object, *, document_type: DocumentType, approved: bool
) -> tuple[list[dict[str, object]], dict[str, str]]:
    if supplied is None:
        supplied = ()
    if isinstance(supplied, (str, bytes)) or not isinstance(supplied, Sequence):
        return [], {"brd_hierarchy": "BRD hierarchy rows must be supplied as an ordered list."}
    rows = list(supplied)
    if document_type is DocumentType.PRD and rows:
        return [], {"brd_hierarchy": "BRD hierarchy rows are available only for BRDs."}
    errors: dict[str, str] = {}
    if approved and document_type is DocumentType.BRD and not rows:
        errors["brd_hierarchy"] = "At least one complete BRD hierarchy row is required before approval."
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, supplied_row in enumerate(rows, start=1):
        prefix = f"brd_hierarchy.{index}"
        if not isinstance(supplied_row, Mapping):
            errors[prefix] = "Each BRD hierarchy entry must be a structured row."
            continue
        row = dict(supplied_row)
        for unknown in set(row) - set(BRD_HIERARCHY_FIELDS):
            errors[f"{prefix}.{unknown}"] = "Unknown BRD hierarchy field."
        raw_row_id = row.get("row_id", "")
        row_id = raw_row_id.strip() if isinstance(raw_row_id, str) else ""
        if row_id and (not is_stable_identifier(row_id) or row_id in seen_ids):
            errors[f"{prefix}.row_id"] = "BRD hierarchy row ID must be stable and unique."
        if row_id:
            seen_ids.add(row_id)
        row_requires_approval = approved and not row_id.startswith("legacy-")
        item: dict[str, object] = {"row_id": row_id, "position": index}
        prior_id = ""
        for level in BRD_HIERARCHY_LEVELS:
            raw_id = row.get(f"{level}_id", "")
            item_id = raw_id.strip() if isinstance(raw_id, str) else ""
            if item_id and (not is_stable_identifier(item_id) or item_id in seen_ids):
                errors[f"{prefix}.{level}_id"] = f"{level.replace('_', ' ').title()} ID must be stable and unique."
            if item_id:
                seen_ids.add(item_id)
            raw_text = row.get(level, "")
            text = normalize_text(raw_text) if isinstance(raw_text, str) else ""
            if not isinstance(raw_text, str):
                errors[f"{prefix}.{level}"] = f"{level.replace('_', ' ').title()} must be text."
            if row_requires_approval and not text:
                errors[f"{prefix}.{level}"] = f"{level.replace('_', ' ').title()} is required before BRD approval."
            parent_field = f"{level}_parent_id"
            parent_id = "" if level == "epic" else normalize_text(str(row.get(parent_field, "")))
            if level != "epic" and row_requires_approval and parent_id != prior_id:
                errors[f"{prefix}.{parent_field}"] = f"{level.replace('_', ' ').title()} must reference its preceding parent in this hierarchy row."
            criteria_field = f"{level}_acceptance_criteria"
            raw_criteria = row.get(criteria_field, ())
            if isinstance(raw_criteria, (str, bytes)) or not isinstance(raw_criteria, Sequence):
                errors[f"{prefix}.{criteria_field}"] = "Acceptance criteria must be an ordered list."
                raw_criteria = ()
            criteria: list[dict[str, object]] = []
            for criterion_index, raw_criterion in enumerate(raw_criteria, start=1):
                criterion_prefix = f"{prefix}.{criteria_field}.{criterion_index}"
                if not isinstance(raw_criterion, Mapping):
                    errors[criterion_prefix] = "Each acceptance criterion must be structured."
                    continue
                criterion_id_raw = raw_criterion.get("criterion_id", "")
                criterion_id = criterion_id_raw.strip() if isinstance(criterion_id_raw, str) else ""
                if criterion_id and (not is_stable_identifier(criterion_id) or criterion_id in seen_ids):
                    errors[f"{criterion_prefix}.criterion_id"] = "Criterion ID must be stable and unique."
                if criterion_id:
                    seen_ids.add(criterion_id)
                criterion_text_raw = raw_criterion.get("text", "")
                criterion_text = normalize_text(criterion_text_raw) if isinstance(criterion_text_raw, str) else ""
                if row_requires_approval and not criterion_text:
                    errors[f"{criterion_prefix}.text"] = "A measurable criterion is required before BRD approval."
                criteria.append({"criterion_id": criterion_id, "position": criterion_index, "text": criterion_text})
            if row_requires_approval and not criteria:
                errors[f"{prefix}.{criteria_field}"] = f"{level.replace('_', ' ').title()} acceptance criteria are required before BRD approval."
            item.update({f"{level}_id": item_id, level: text, criteria_field: criteria})
            if level != "epic":
                item[parent_field] = parent_id
            prior_id = item_id
        normalized.append(item)
    return normalized, errors


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
            structured_replacements = set()
            if document_type is DocumentType.PRD:
                if "contributors" in supplied_data:
                    structured_replacements.add("contributors_roles")
                if "key_dates_milestones" in supplied_data:
                    structured_replacements.update({"key_dates", "milestones"})
            else:
                if "brd_hierarchy" in supplied_data:
                    structured_replacements.update({
                        "epics", "capabilities", "features", "user_stories",
                        "acceptance_criteria",
                    })
                if "brd_risks" in supplied_data:
                    structured_replacements.update({"business_risks", "mitigation_strategies"})
            if (
                document_status is DocumentStatus.APPROVED
                and not normalized
                and definition.key not in structured_replacements
            ):
                approval_label = (
                    "Non-goals"
                    if definition.key == "non_goals"
                    else definition.label
                )
                errors[error_key] = (
                    f"{approval_label} is required before approval."
                )
                continue
            normalized_sections[definition.key] = normalized

        for key in supplied_sections:
            if key not in known_keys:
                errors[f"sections.{key}"] = "Unknown document section."
        normalized_data["sections"] = normalized_sections

    if document_type is not None:
        success_matrix, matrix_errors = _validate_success_matrix(
            supplied_data.get("success_matrix", ()),
            document_type=document_type,
            document_status=document_status,
        )
        normalized_data["success_matrix"] = success_matrix
        errors.update(matrix_errors)
        agile_hierarchy, hierarchy_errors = _validate_prd_agile_hierarchy(
            supplied_data.get("agile_hierarchy", ()),
            document_type=document_type,
            document_status=document_status,
        )
        normalized_data["agile_hierarchy"] = agile_hierarchy
        errors.update(hierarchy_errors)

        sections = normalized_data.get("sections", {})
        assert isinstance(sections, Mapping)
        approved = document_status is DocumentStatus.APPROVED

        contributors_were_supplied = "contributors" in supplied_data
        contributors_supplied = supplied_data.get("contributors")
        if contributors_supplied is None and document_type is DocumentType.PRD:
            legacy = str(sections.get("contributors_roles", "")).strip()
            contributors_supplied = (
                [{"entry_id": _legacy_row_id("contributor"), "contributor_name": legacy, "contributor_role": ""}]
                if legacy else []
            )
        contributors, contributor_errors = _structured_rows(
            contributors_supplied or (), field="contributors", fields=CONTRIBUTOR_FIELDS,
            text_fields=("contributor_name", "contributor_role"),
            approved=(approved and document_type is DocumentType.PRD and contributors_were_supplied),
            required_label="contributor and role",
        )
        if document_type is DocumentType.BRD and contributors:
            contributor_errors["contributors"] = "Structured contributors are available only for PRDs."
        normalized_data["contributors"] = contributors
        errors.update(contributor_errors)

        milestones_were_supplied = "key_dates_milestones" in supplied_data
        milestones_supplied = supplied_data.get("key_dates_milestones")
        if milestones_supplied is None and document_type is DocumentType.PRD:
            legacy_date = str(sections.get("key_dates", "")).strip()
            legacy_milestone = str(sections.get("milestones", "")).strip()
            milestones_supplied = (
                [{"entry_id": _legacy_row_id("milestone"), "date": legacy_date, "milestone": legacy_milestone}]
                if legacy_date or legacy_milestone else []
            )
        milestones, milestone_errors = _structured_rows(
            milestones_supplied or (), field="key_dates_milestones", fields=MILESTONE_FIELDS,
            text_fields=("date", "milestone"),
            approved=(approved and document_type is DocumentType.PRD and milestones_were_supplied),
            required_label="key date and milestone",
        )
        if document_type is DocumentType.BRD and milestones:
            milestone_errors["key_dates_milestones"] = "Key Dates and Milestones entries are available only for PRDs."
        normalized_data["key_dates_milestones"] = milestones
        errors.update(milestone_errors)

        brd_hierarchy_was_supplied = "brd_hierarchy" in supplied_data
        brd_hierarchy_supplied = supplied_data.get("brd_hierarchy")
        if brd_hierarchy_supplied is None and document_type is DocumentType.BRD:
            legacy_section_keys = {
                "epic": "epics", "capability": "capabilities",
                "feature": "features", "user_story": "user_stories",
            }
            legacy_values = {
                level: str(sections.get(legacy_section_keys[level], "")).strip()
                for level in BRD_HIERARCHY_LEVELS
            }
            legacy_criterion = str(sections.get("acceptance_criteria", "")).strip()
            if any(legacy_values.values()) or legacy_criterion:
                ids = {level: _legacy_row_id(f"brd-{level}") for level in BRD_HIERARCHY_LEVELS}
                brd_hierarchy_supplied = [{
                    "row_id": _legacy_row_id("brd-hierarchy"),
                    **{f"{level}_id": ids[level] for level in BRD_HIERARCHY_LEVELS},
                    **legacy_values,
                    "capability_parent_id": ids["epic"],
                    "feature_parent_id": ids["capability"],
                    "user_story_parent_id": ids["feature"],
                    "epic_acceptance_criteria": [],
                    "capability_acceptance_criteria": [],
                    "feature_acceptance_criteria": [],
                    "user_story_acceptance_criteria": ([{"criterion_id": _legacy_row_id("brd-user-story-criterion"), "text": legacy_criterion}] if legacy_criterion else []),
                }]
            else:
                brd_hierarchy_supplied = []
        brd_hierarchy, brd_hierarchy_errors = _validate_brd_hierarchy(
            brd_hierarchy_supplied or (), document_type=document_type,
            approved=(approved and document_type is DocumentType.BRD and brd_hierarchy_was_supplied),
        )
        normalized_data["brd_hierarchy"] = brd_hierarchy
        errors.update(brd_hierarchy_errors)

        risks_were_supplied = "brd_risks" in supplied_data
        risks_supplied = supplied_data.get("brd_risks")
        if risks_supplied is None and document_type is DocumentType.BRD:
            legacy_risk = str(sections.get("business_risks", "")).strip()
            legacy_mitigation = str(sections.get("mitigation_strategies", "")).strip()
            risks_supplied = (
                [{"entry_id": _legacy_row_id("brd-risk"), "business_risk": legacy_risk, "mitigation_strategy": legacy_mitigation}]
                if legacy_risk or legacy_mitigation else []
            )
        risks, risk_errors = _structured_rows(
            risks_supplied or (), field="brd_risks", fields=BRD_RISK_FIELDS,
            text_fields=("business_risk", "mitigation_strategy"),
            approved=(approved and document_type is DocumentType.BRD and risks_were_supplied),
            required_label="business risk and mitigation strategy",
        )
        if document_type is DocumentType.PRD and risks:
            risk_errors["brd_risks"] = "Business Risk and Mitigation Strategy entries are available only for BRDs."
        normalized_data["brd_risks"] = risks
        errors.update(risk_errors)

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
