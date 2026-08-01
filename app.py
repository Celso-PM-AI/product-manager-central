"""Streamlit interface for Product Manager Central."""

import os
import sqlite3
from collections.abc import Callable
from typing import Final

import streamlit as st

from src.database import (
    DATABASE_FILE,
    DatabaseSchemaError,
    ProductValidationError,
    DocumentAssociationError,
    DocumentValidationError,
    count_documents_for_product,
    create_document,
    create_product,
    delete_product,
    get_dashboard_metrics,
    get_document,
    get_product,
    initialize_database,
    list_documents_for_product,
    list_products,
    search_products,
    update_document,
    update_product,
)
from src.document_templates import (
    derived_document_title,
    document_template,
    prepopulated_sections,
)
from src.models import (
    DEFAULT_PRODUCT_STATUS,
    DocumentStatus,
    DocumentType,
    Product,
    ProductDocument,
    ProductStatus,
)
from src.validation import (
    DOCUMENT_SECTION_MAX_LENGTH,
    DOCUMENT_TITLE_MAX_LENGTH,
    DOCUMENT_VERSION_MAX_LENGTH,
    TEXT_FIELD_MAX_LENGTHS,
    validate_document,
    validate_product,
)


APP_TITLE: Final[str] = "Product Manager Central"
APP_DATABASE_FILE: Final[str] = os.environ.get("PMC_DATABASE_FILE", DATABASE_FILE)
NAVIGATION_OPTIONS: Final[tuple[str, ...]] = (
    "Dashboard",
    "Create Product",
    "Create PRD",
    "Create BRD",
    "View Products",
    "Search Products",
)
DETAIL_MODE: Final[str] = "detail"
EDIT_MODE: Final[str] = "edit"
DELETE_CONFIRM_MODE: Final[str] = "delete_confirm"
NAVIGATION_STATE_KEY: Final[str] = "navigation_section"
PENDING_NAVIGATION_KEY: Final[str] = "_pending_navigation"
PENDING_STATE_CLEANUP_KEY: Final[str] = "_pending_state_cleanup"
WORKFLOW_FLASH_KEY: Final[str] = "_product_workflow_flash"
DOCUMENT_LIST_MODE: Final[str] = "document_list"
DOCUMENT_CHOOSE_MODE: Final[str] = "document_choose"
DOCUMENT_CREATE_MODE: Final[str] = "document_create"
DOCUMENT_PREVIEW_MODE: Final[str] = "document_preview"
DOCUMENT_EDIT_MODE: Final[str] = "document_edit"


def status_label(status: ProductStatus) -> str:
    """Return a readable label for a canonical product status."""

    return status.value.replace("_", " ").title()


def document_status_label(status: DocumentStatus) -> str:
    """Return a readable label for a document approval status."""

    return status.value.title()


def document_option_label(document: ProductDocument) -> str:
    """Return an ID-safe label for an associated document selector."""

    return (
        f"{document.title} · {document.document_type.value} · "
        f"Version {document.version} · ID {document.id}"
    )


def product_option_label(product: Product) -> str:
    """Return a compact, ID-safe label for a product selector."""

    return f"{product.name} · {status_label(product.status)} · ID {product.id}"


def target_users_summary(target_users: str, limit: int = 90) -> str:
    """Create a compact single-line target-user summary."""

    summary = " ".join(target_users.split())
    if len(summary) <= limit:
        return summary
    return f"{summary[: limit - 1].rstrip()}…"


def display_database_error(operation: str = "accessed") -> None:
    """Show a user-safe persistence error without exposing SQL details."""

    st.error(
        f"Product data could not be {operation}. "
        "Please check the local database and try again."
    )


def display_validation_errors(errors: dict[str, str]) -> None:
    """Display every centralized validation error together."""

    st.error("Please correct the following fields before saving:")
    for message in errors.values():
        st.markdown(f"- {message}")


def editable_product_values(product: Product | None = None) -> dict[str, object]:
    """Return form-ready values for create or edit without system fields."""

    if product is None:
        return {
            "name": "",
            "description": "",
            "target_users": "",
            "business_goal": "",
            "status": DEFAULT_PRODUCT_STATUS,
            "customer_problem": "",
            "product_strategy": "",
            "notes": "",
        }

    return {
        "name": product.name,
        "description": product.description,
        "target_users": product.target_users,
        "business_goal": product.business_goal,
        "status": product.status,
        "customer_problem": product.customer_problem or "",
        "product_strategy": product.product_strategy or "",
        "notes": product.notes or "",
    }


def render_product_fields(
    *,
    key_prefix: str,
    product: Product | None = None,
) -> dict[str, object]:
    """Render every editable field and return the submitted values."""

    values = editable_product_values(product)
    name = st.text_input(
        "Name *",
        value=values["name"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["name"],
        help="A clear product name.",
        key=f"{key_prefix}_name",
    )
    description = st.text_area(
        "Description *",
        value=values["description"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["description"],
        help="What the product is and what it enables.",
        key=f"{key_prefix}_description",
    )
    target_users = st.text_area(
        "Target users *",
        value=values["target_users"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["target_users"],
        help="The people or groups this product serves.",
        key=f"{key_prefix}_target_users",
    )
    business_goal = st.text_area(
        "Business goal *",
        value=values["business_goal"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["business_goal"],
        help="The business outcome this product should support.",
        key=f"{key_prefix}_business_goal",
    )
    status = st.selectbox(
        "Status *",
        options=list(ProductStatus),
        index=list(ProductStatus).index(values["status"]),
        format_func=status_label,
        key=f"{key_prefix}_status",
    )

    st.subheader("Optional context")
    customer_problem = st.text_area(
        "Customer problem",
        value=values["customer_problem"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["customer_problem"],
        key=f"{key_prefix}_customer_problem",
    )
    product_strategy = st.text_area(
        "Product strategy",
        value=values["product_strategy"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["product_strategy"],
        key=f"{key_prefix}_product_strategy",
    )
    notes = st.text_area(
        "Notes",
        value=values["notes"],
        max_chars=TEXT_FIELD_MAX_LENGTHS["notes"],
        key=f"{key_prefix}_notes",
    )

    return {
        "name": name,
        "description": description,
        "target_users": target_users,
        "business_goal": business_goal,
        "status": status,
        "customer_problem": customer_problem,
        "product_strategy": product_strategy,
        "notes": notes,
    }


def document_action_state_keys(selector_key: str) -> tuple[str, str, str, str]:
    """Return product-bound state keys for a document workflow."""

    return (
        f"{selector_key}_document_mode",
        f"{selector_key}_document_product_id",
        f"{selector_key}_document_id",
        f"{selector_key}_document_type",
    )


def set_document_action(
    selector_key: str,
    product_id: int,
    mode: str,
    *,
    document_id: int | None = None,
    document_type: DocumentType | None = None,
) -> None:
    """Set an associated-document workflow using stable IDs."""

    mode_key, product_key, document_key, type_key = document_action_state_keys(
        selector_key
    )
    st.session_state[mode_key] = mode
    st.session_state[product_key] = product_id
    if document_id is None:
        st.session_state.pop(document_key, None)
    else:
        st.session_state[document_key] = document_id
    if document_type is None:
        st.session_state.pop(type_key, None)
    else:
        st.session_state[type_key] = document_type


def current_document_action(selector_key: str, product_id: int) -> str:
    """Return document mode, resetting state left by a different product."""

    mode_key, product_key, _, _ = document_action_state_keys(selector_key)
    if st.session_state.get(product_key) != product_id:
        set_document_action(selector_key, product_id, DOCUMENT_LIST_MODE)
    return str(st.session_state.get(mode_key, DOCUMENT_LIST_MODE))


def editable_document_values(
    product: Product,
    document_type: DocumentType,
    document: ProductDocument | None = None,
) -> dict[str, object]:
    """Return prepopulated create values or a saved editing snapshot."""

    if document is not None:
        return {
            "title": document.title,
            "version": document.version,
            "document_status": document.document_status,
            "sections": dict(document.sections),
        }
    return {
        "title": derived_document_title(product, document_type),
        "version": "1.0",
        "document_status": DocumentStatus.DRAFT,
        "sections": prepopulated_sections(product, document_type),
    }


def render_document_fields(
    *,
    key_prefix: str,
    product: Product,
    document_type: DocumentType,
    document: ProductDocument | None = None,
) -> dict[str, object]:
    """Render shared metadata and template-driven BRD or PRD sections."""

    values = editable_document_values(product, document_type, document)
    title = st.text_input(
        "Document title *",
        value=values["title"],
        max_chars=DOCUMENT_TITLE_MAX_LENGTH,
        help="A clear title for this saved document.",
        key=f"{key_prefix}_title",
    )
    version = st.text_input(
        "Version *",
        value=values["version"],
        max_chars=DOCUMENT_VERSION_MAX_LENGTH,
        help="Free text such as 1.0, v2, or 2026-Q3.",
        key=f"{key_prefix}_version",
    )
    document_status = st.selectbox(
        "Document status *",
        options=list(DocumentStatus),
        index=list(DocumentStatus).index(values["document_status"]),
        format_func=document_status_label,
        help=(
            "Drafts may contain empty sections. Every section must be complete "
            "before the document can be Approved."
        ),
        key=f"{key_prefix}_status",
    )

    st.markdown("#### Guided sections")
    sections: dict[str, str] = {}
    for definition in document_template(document_type):
        sections[definition.key] = st.text_area(
            definition.label,
            value=values["sections"].get(definition.key, ""),
            max_chars=DOCUMENT_SECTION_MAX_LENGTH,
            help=definition.guidance,
            key=f"{key_prefix}_section_{definition.key}",
        )
    return {
        "title": title,
        "version": version,
        "document_status": document_status,
        "sections": sections,
    }


def action_state_keys(selector_key: str) -> tuple[str, str]:
    """Return session-state keys for one product selector's workflow."""

    return (
        f"{selector_key}_action_mode",
        f"{selector_key}_action_product_id",
    )


def set_product_action(
    selector_key: str,
    product_id: int,
    mode: str,
) -> None:
    """Set the current ID-bound detail action."""

    mode_key, product_id_key = action_state_keys(selector_key)
    st.session_state[mode_key] = mode
    st.session_state[product_id_key] = product_id


def current_product_action(selector_key: str, product_id: int) -> str:
    """Return the action for this product, resetting stale ID-bound state."""

    mode_key, product_id_key = action_state_keys(selector_key)
    if st.session_state.get(product_id_key) != product_id:
        set_product_action(selector_key, product_id, DETAIL_MODE)
    return str(st.session_state.get(mode_key, DETAIL_MODE))


def request_state_cleanup(*keys: str) -> None:
    """Schedule widget-safe session cleanup before the next app rerun."""

    pending = set(st.session_state.get(PENDING_STATE_CLEANUP_KEY, ()))
    pending.update(keys)
    st.session_state[PENDING_STATE_CLEANUP_KEY] = tuple(pending)


def apply_pending_state_changes() -> None:
    """Apply navigation and cleanup requests before widgets are created."""

    for key in st.session_state.pop(PENDING_STATE_CLEANUP_KEY, ()):
        st.session_state.pop(key, None)

    requested_navigation = st.session_state.pop(PENDING_NAVIGATION_KEY, None)
    if requested_navigation in NAVIGATION_OPTIONS:
        st.session_state[NAVIGATION_STATE_KEY] = requested_navigation


def set_workflow_flash(level: str, message: str) -> None:
    """Store a one-rerun workflow message."""

    st.session_state[WORKFLOW_FLASH_KEY] = (level, message)


def display_workflow_flash() -> None:
    """Display and consume a pending workflow message."""

    flash = st.session_state.pop(WORKFLOW_FLASH_KEY, None)
    if flash is None:
        return

    level, message = flash
    display = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }.get(level, st.info)
    display(message)


def display_product_details(product: Product) -> None:
    """Render every canonical field for one saved product."""

    st.subheader(product.name)
    st.caption(f"Product ID {product.id} · {status_label(product.status)}")

    core_fields = (
        ("Description", product.description),
        ("Target users", product.target_users),
        ("Business goal", product.business_goal),
        ("Status", status_label(product.status)),
    )
    for label, value in core_fields:
        st.markdown(f"**{label}**")
        st.write(value)

    st.divider()
    st.markdown("#### Optional context")
    optional_fields = (
        ("Customer problem", product.customer_problem),
        ("Product strategy", product.product_strategy),
        ("Notes", product.notes),
    )
    for label, value in optional_fields:
        st.markdown(f"**{label}**")
        st.write(value or "Not provided")

    st.caption(
        f"Created: {product.created_at or 'Not available'}  ·  "
        f"Updated: {product.updated_at or 'Not available'}"
    )


def display_document_preview(document: ProductDocument, product: Product) -> None:
    """Render a formatted, deterministic document preview."""

    st.subheader(document.title)
    st.caption(
        f"{document.document_type.value} · Document ID {document.id} · "
        f"Version {document.version} · "
        f"{document_status_label(document.document_status)}"
    )
    st.markdown(f"**Associated product:** {product.name} (ID {product.id})")
    st.divider()
    for definition in document_template(document.document_type):
        st.markdown(f"### {definition.label}")
        st.write(document.sections.get(definition.key) or "Not provided")
    st.caption(
        f"Created: {document.created_at or 'Not available'}  ·  "
        f"Updated: {document.updated_at or 'Not available'}"
    )


def render_document_editor(
    product: Product,
    document_type: DocumentType,
    *,
    selector_key: str,
    document: ProductDocument | None = None,
    on_create_cancel: Callable[[], None] | None = None,
) -> None:
    """Render and save a shared create or edit form."""

    if product.id is None:
        st.warning("Documents require a saved product ID.")
        return

    action = "Edit" if document is not None else "Create"
    st.markdown(f"### {action} {document_type.value}")
    st.caption(
        "This document uses a structured template. It does not call an AI or LLM."
    )
    identity = document.id if document is not None else "new"
    form_key = f"{selector_key}_document_form_{identity}_{document_type.value}"
    with st.form(form_key):
        editable = render_document_fields(
            key_prefix=form_key,
            product=product,
            document_type=document_type,
            document=document,
        )
        save_column, cancel_column = st.columns(2)
        save = save_column.form_submit_button(
            "Save document",
            type="primary",
            width="stretch",
        )
        cancel = cancel_column.form_submit_button("Cancel", width="stretch")

    if cancel:
        if document is None:
            if on_create_cancel is None:
                set_document_action(selector_key, product.id, DOCUMENT_LIST_MODE)
            else:
                on_create_cancel()
        else:
            set_document_action(
                selector_key,
                product.id,
                DOCUMENT_PREVIEW_MODE,
                document_id=document.id,
            )
        st.rerun()
    if not save:
        return

    document_data = {
        "product_id": product.id,
        "document_type": document_type,
        **editable,
    }
    validation_result = validate_document(document_data)
    if not validation_result.is_valid:
        display_validation_errors(validation_result.errors)
        return

    try:
        if document is None:
            saved = create_document(
                validation_result.normalized_data,
                APP_DATABASE_FILE,
            )
            message = f'"{saved.title}" was created as document ID {saved.id}.'
        else:
            saved = update_document(
                document.id,
                editable,
                APP_DATABASE_FILE,
            )
            if saved is None:
                st.warning("This document no longer exists and could not be updated.")
                return
            message = f'"{saved.title}" was updated successfully.'
    except DocumentValidationError as error:
        display_validation_errors(error.errors)
        return
    except DocumentAssociationError:
        st.warning("The associated product no longer exists.")
        return
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error("saved")
        return

    set_document_action(
        selector_key,
        product.id,
        DOCUMENT_PREVIEW_MODE,
        document_id=saved.id,
    )
    set_workflow_flash("success", message)
    st.rerun()


def render_document_preview_or_edit(
    product: Product,
    *,
    selector_key: str,
    mode: str,
    on_preview_back: Callable[[], None] | None = None,
    preview_back_label: str = "Back to documents",
) -> bool:
    """Render shared stable-ID preview or edit state when active."""

    if product.id is None or mode not in {
        DOCUMENT_PREVIEW_MODE,
        DOCUMENT_EDIT_MODE,
    }:
        return False

    _, _, document_key, _ = document_action_state_keys(selector_key)
    document_id = st.session_state.get(document_key)
    try:
        document = (
            get_document(document_id, APP_DATABASE_FILE)
            if isinstance(document_id, int)
            else None
        )
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return True

    if document is None or document.product_id != product.id:
        st.warning("That document is no longer available for this product.")
        set_document_action(selector_key, product.id, DOCUMENT_LIST_MODE)
        return True

    if mode == DOCUMENT_EDIT_MODE:
        render_document_editor(
            product,
            document.document_type,
            selector_key=selector_key,
            document=document,
        )
        return True

    display_document_preview(document, product)
    edit_column, back_column = st.columns(2)
    if edit_column.button(
        "Edit document",
        type="primary",
        width="stretch",
        key=f"{selector_key}_edit_document_{document.id}",
    ):
        set_document_action(
            selector_key,
            product.id,
            DOCUMENT_EDIT_MODE,
            document_id=document.id,
        )
        st.rerun()
    if back_column.button(
        preview_back_label,
        width="stretch",
        key=f"{selector_key}_back_documents_{document.id}",
    ):
        if on_preview_back is None:
            set_document_action(selector_key, product.id, DOCUMENT_LIST_MODE)
        else:
            on_preview_back()
        st.rerun()
    return True


def render_product_documents(product: Product, *, selector_key: str) -> None:
    """Render create, list, preview, and edit states for one product's documents."""

    if product.id is None:
        return
    mode = current_document_action(selector_key, product.id)
    mode_key, _, _, type_key = document_action_state_keys(selector_key)

    st.divider()
    st.subheader("Product documents")

    if mode == DOCUMENT_CHOOSE_MODE:
        st.write("Choose the structured template for the new document.")
        document_type = st.radio(
            "Document type",
            options=list(DocumentType),
            format_func=lambda value: value.value,
            horizontal=True,
            key=f"{selector_key}_new_document_type",
        )
        continue_column, cancel_column = st.columns(2)
        if continue_column.button(
            "Continue",
            type="primary",
            width="stretch",
            key=f"{selector_key}_continue_document",
        ):
            set_document_action(
                selector_key,
                product.id,
                DOCUMENT_CREATE_MODE,
                document_type=document_type,
            )
            st.rerun()
        if cancel_column.button(
            "Cancel",
            width="stretch",
            key=f"{selector_key}_cancel_new_document",
        ):
            set_document_action(selector_key, product.id, DOCUMENT_LIST_MODE)
            st.rerun()
        return

    if mode == DOCUMENT_CREATE_MODE:
        document_type = st.session_state.get(type_key)
        if not isinstance(document_type, DocumentType):
            st.session_state[mode_key] = DOCUMENT_CHOOSE_MODE
            st.rerun()
        render_document_editor(
            product,
            document_type,
            selector_key=selector_key,
        )
        return

    if render_document_preview_or_edit(
        product,
        selector_key=selector_key,
        mode=mode,
    ):
        return

    try:
        documents = list_documents_for_product(product.id, APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if st.button(
        "Create Document",
        type="primary",
        key=f"{selector_key}_create_document_{product.id}",
    ):
        set_document_action(selector_key, product.id, DOCUMENT_CHOOSE_MODE)
        st.rerun()

    if not documents:
        st.info(
            "No documents yet. Create a BRD or PRD from this product's saved context."
        )
        return

    st.caption(
        f"{len(documents)} document{'s' if len(documents) != 1 else ''} "
        "associated with this product"
    )
    st.dataframe(
        [
            {
                "ID": document.id,
                "Type": document.document_type.value,
                "Title": document.title,
                "Version": document.version,
                "Status": document_status_label(document.document_status),
                "Updated": document.updated_at,
            }
            for document in documents
        ],
        width="stretch",
        hide_index=True,
    )
    documents_by_id = {document.id: document for document in documents}
    selected_id = st.selectbox(
        "Select a document",
        options=list(documents_by_id),
        format_func=lambda value: document_option_label(documents_by_id[value]),
        key=f"{selector_key}_document_selector",
    )
    if st.button(
        "Preview document",
        key=f"{selector_key}_preview_document",
    ):
        set_document_action(
            selector_key,
            product.id,
            DOCUMENT_PREVIEW_MODE,
            document_id=selected_id,
        )
        st.rerun()


def reset_primary_document_flow(
    selector_key: str,
) -> None:
    """Schedule a widget-safe return to a primary document product selector."""

    request_state_cleanup(
        f"{selector_key}_product_selector",
        *document_action_state_keys(selector_key),
    )


def render_primary_document_creation(document_type: DocumentType) -> None:
    """Render an ID-safe product selector and the shared document workflow."""

    document_label = document_type.value
    selector_key = f"primary_create_{document_label.lower()}"
    st.header(f"Create {document_label}")
    st.write(
        f"Select the product that this {document_label} should be associated with."
    )
    display_workflow_flash()

    try:
        products = list_products(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if not products:
        st.info("A product must be created before you can create a BRD or PRD.")
        st.write("Use Create Product to add the first product, then return here.")
        if st.button(
            "Go to Create Product",
            type="primary",
            key=f"{selector_key}_go_to_create_product",
        ):
            reset_primary_document_flow(selector_key)
            st.session_state[PENDING_NAVIGATION_KEY] = "Create Product"
            st.rerun()
        return

    products_by_id = {
        product.id: product for product in products if product.id is not None
    }
    selected_id = st.selectbox(
        "Select a product",
        options=[None, *products_by_id],
        format_func=(
            lambda product_id: (
                "Select a product"
                if product_id is None
                else product_option_label(products_by_id[product_id])
            )
        ),
        key=f"{selector_key}_product_selector",
    )
    if selected_id is None:
        st.info(f"Select a product to begin the {document_label}.")
        return

    try:
        selected_product = get_product(selected_id, APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return
    if selected_product is None:
        st.warning("The associated product no longer exists.")
        return

    mode_key, product_key, _, _ = document_action_state_keys(selector_key)
    if st.session_state.get(product_key) != selected_id:
        set_document_action(
            selector_key,
            selected_id,
            DOCUMENT_CREATE_MODE,
            document_type=document_type,
        )

    mode = str(st.session_state.get(mode_key, DOCUMENT_CREATE_MODE))

    def on_return() -> None:
        reset_primary_document_flow(selector_key)

    if render_document_preview_or_edit(
        selected_product,
        selector_key=selector_key,
        mode=mode,
        on_preview_back=on_return,
        preview_back_label="Back to product selection",
    ):
        return

    if mode != DOCUMENT_CREATE_MODE:
        set_document_action(
            selector_key,
            selected_id,
            DOCUMENT_CREATE_MODE,
            document_type=document_type,
        )
    render_document_editor(
        selected_product,
        document_type,
        selector_key=selector_key,
        on_create_cancel=on_return,
    )


def render_dashboard() -> None:
    """Render the approved product metrics."""

    st.header("Dashboard")
    st.write("A quick overview of your saved product portfolio.")

    try:
        metrics = get_dashboard_metrics(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    columns = st.columns(4)
    metric_items = (
        ("Total products", metrics["total_products"]),
        ("Active products", metrics["active_products"]),
        ("Launched products", metrics["launched_products"]),
        ("Updated in last 30 days", metrics["recently_updated_products"]),
    )
    for column, (label, value) in zip(columns, metric_items, strict=True):
        column.metric(label, value)

    st.caption(
        "Active excludes archived products. Recently updated covers the "
        "previous 30 days."
    )
    if metrics["total_products"] == 0:
        st.info(
            "No products yet. Use Create Product to add the first product "
            "to your workspace."
        )


def render_create_product() -> None:
    """Render the canonical create form and save only validated data."""

    st.header("Create Product")
    st.write(
        "Capture the essential context for a product. "
        "Fields marked with * are required."
    )

    with st.form("create_product_form"):
        product_data = render_product_fields(key_prefix="create_product")
        submitted = st.form_submit_button(
            "Create product",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    validation_result = validate_product(product_data)
    if not validation_result.is_valid:
        display_validation_errors(validation_result.errors)
        return

    try:
        product = create_product(
            validation_result.normalized_data,
            APP_DATABASE_FILE,
        )
    except ProductValidationError as error:
        display_validation_errors(error.errors)
        return
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error("saved")
        return

    st.success(f'"{product.name}" was created successfully as product ID {product.id}.')
    st.info("Open View Products to review the complete saved record.")


def render_edit_product(product: Product, *, selector_key: str) -> None:
    """Render a prepopulated edit form and save only valid changes."""

    if product.id is None:
        st.warning("This product cannot be edited because it has no saved ID.")
        return

    st.subheader(f"Edit {product.name}")
    st.caption(
        f"Product ID {product.id}. The ID and original creation time are preserved."
    )
    form_key = f"{selector_key}_edit_{product.id}"
    with st.form(form_key):
        product_data = render_product_fields(
            key_prefix=form_key,
            product=product,
        )
        save_column, cancel_column = st.columns(2)
        save = save_column.form_submit_button(
            "Save changes",
            type="primary",
            width="stretch",
        )
        cancel = cancel_column.form_submit_button(
            "Cancel",
            width="stretch",
        )

    if cancel:
        set_product_action(selector_key, product.id, DETAIL_MODE)
        st.rerun()
    if not save:
        return

    validation_result = validate_product(product_data)
    if not validation_result.is_valid:
        display_validation_errors(validation_result.errors)
        return

    try:
        updated = update_product(
            product.id,
            validation_result.normalized_data,
            APP_DATABASE_FILE,
        )
    except ProductValidationError as error:
        display_validation_errors(error.errors)
        return
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error("updated")
        return

    if updated is None:
        set_product_action(selector_key, product.id, DETAIL_MODE)
        st.warning("This product no longer exists and could not be updated.")
        return

    set_product_action(selector_key, product.id, DETAIL_MODE)
    set_workflow_flash(
        "success",
        f'"{updated.name}" was updated successfully.',
    )
    st.rerun()


def render_delete_confirmation(product: Product, *, selector_key: str) -> None:
    """Render the explicit second deletion step for one product ID."""

    if product.id is None:
        st.warning("This product cannot be deleted because it has no saved ID.")
        return

    try:
        document_count = count_documents_for_product(
            product.id,
            APP_DATABASE_FILE,
        )
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    document_warning = (
        f" It will also permanently delete {document_count} associated "
        f"document{'s' if document_count != 1 else ''}."
        if document_count
        else " It has no associated documents."
    )
    st.warning(
        f'You are about to permanently delete "{product.name}" '
        f"(product ID {product.id}).{document_warning} This action cannot be undone."
    )
    confirm_column, cancel_column = st.columns(2)
    confirmed = confirm_column.button(
        "Delete permanently",
        type="primary",
        width="stretch",
        key=f"{selector_key}_confirm_delete_{product.id}",
    )
    canceled = cancel_column.button(
        "Cancel",
        width="stretch",
        key=f"{selector_key}_cancel_delete_{product.id}",
    )

    if canceled:
        set_product_action(selector_key, product.id, DETAIL_MODE)
        st.rerun()
    if not confirmed:
        return

    try:
        deleted = delete_product(product.id, APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error("deleted")
        return

    mode_key, product_id_key = action_state_keys(selector_key)
    request_state_cleanup(
        selector_key,
        mode_key,
        product_id_key,
        "view_product_selector",
        "search_product_selector",
    )
    st.session_state[PENDING_NAVIGATION_KEY] = "View Products"

    if deleted:
        set_workflow_flash(
            "success",
            f'"{product.name}" (product ID {product.id}) was permanently deleted.',
        )
    else:
        set_workflow_flash(
            "warning",
            f'"{product.name}" (product ID {product.id}) was already deleted.',
        )
    st.rerun()


def render_product_actions(product: Product, *, selector_key: str) -> None:
    """Render ID-bound detail, edit, and two-step delete states."""

    if product.id is None:
        display_product_details(product)
        return

    mode = current_product_action(selector_key, product.id)
    if mode == EDIT_MODE:
        render_edit_product(product, selector_key=selector_key)
        return

    display_product_details(product)
    if mode == DELETE_CONFIRM_MODE:
        st.divider()
        render_delete_confirmation(product, selector_key=selector_key)
        return

    edit_column, delete_column = st.columns(2)
    if edit_column.button(
        "Edit",
        type="primary",
        width="stretch",
        key=f"{selector_key}_edit_action_{product.id}",
    ):
        set_product_action(selector_key, product.id, EDIT_MODE)
        st.rerun()
    if delete_column.button(
        "Delete",
        width="stretch",
        key=f"{selector_key}_delete_action_{product.id}",
    ):
        set_product_action(selector_key, product.id, DELETE_CONFIRM_MODE)
        st.rerun()

    render_product_documents(product, selector_key=selector_key)


def render_product_list(
    products: list[Product],
    *,
    empty_message: str,
    selector_key: str,
) -> None:
    """Render a compact list and an ID-based complete-detail selector."""

    if not products:
        st.info(empty_message)
        return

    st.caption(f"{len(products)} product{'s' if len(products) != 1 else ''}")
    rows = [
        {
            "Name": product.name,
            "Status": status_label(product.status),
            "Target users": target_users_summary(product.target_users),
            "Updated": product.updated_at,
        }
        for product in products
    ]
    st.dataframe(rows, width="stretch", hide_index=True)

    products_by_id = {
        product.id: product for product in products if product.id is not None
    }
    product_ids = list(products_by_id)
    selected_id = st.selectbox(
        "Select a product to view",
        options=product_ids,
        format_func=lambda product_id: product_option_label(
            products_by_id[product_id]
        ),
        key=selector_key,
    )

    try:
        selected_product = get_product(selected_id, APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if selected_product is None:
        st.warning("That product is no longer available. Refresh the page.")
        return

    st.divider()
    render_product_actions(selected_product, selector_key=selector_key)


def render_view_products() -> None:
    """Render all saved products and allow one to be opened."""

    st.header("View Products")
    st.write("Review your saved products and open a complete product record.")
    display_workflow_flash()
    try:
        products = list_products(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    render_product_list(
        products,
        empty_message=(
            "No products yet. Use Create Product to add the first product "
            "to your workspace."
        ),
        selector_key="view_product_selector",
    )


def render_search_products() -> None:
    """Render canonical text search and complete result details."""

    st.header("Search Products")
    st.write("Search names, descriptions, users, goals, and optional context.")
    display_workflow_flash()
    query = st.text_input(
        "Search",
        placeholder="Enter a name, user, goal, or keyword",
    )

    try:
        products = search_products(query, APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if query.strip():
        st.write(
            f"{len(products)} result{'s' if len(products) != 1 else ''} "
            f'for "{query.strip()}"'
        )
        empty_message = (
            "No products match this search. Try a different name, user, "
            "goal, or keyword."
        )
    else:
        st.caption("Enter a keyword, or browse all products below.")
        empty_message = (
            "No products yet. Use Create Product to add the first product "
            "to your workspace."
        )

    render_product_list(
        products,
        empty_message=empty_message,
        selector_key="search_product_selector",
    )


def main() -> None:
    """Configure and run the single-page Streamlit application."""

    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📊",
        layout="wide",
    )

    apply_pending_state_changes()

    try:
        initialize_database(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        st.title(APP_TITLE)
        display_database_error()
        st.stop()

    st.sidebar.title(APP_TITLE)
    st.sidebar.caption("Product workspace")
    selected_section = st.sidebar.radio(
        "Navigation",
        NAVIGATION_OPTIONS,
        label_visibility="collapsed",
        key=NAVIGATION_STATE_KEY,
    )

    st.title(APP_TITLE)
    st.caption("A focused workspace for product strategy and context.")

    renderers: dict[str, Callable[[], None]] = {
        "Dashboard": render_dashboard,
        "Create Product": render_create_product,
        "Create PRD": lambda: render_primary_document_creation(DocumentType.PRD),
        "Create BRD": lambda: render_primary_document_creation(DocumentType.BRD),
        "View Products": render_view_products,
        "Search Products": render_search_products,
    }
    renderers[selected_section]()


if __name__ == "__main__":
    main()
