"""Streamlit interface for Product Manager Central."""

import sqlite3
from collections.abc import Callable
from typing import Final

import streamlit as st

from src.database import (
    DatabaseSchemaError,
    ProductValidationError,
    create_product,
    get_dashboard_metrics,
    get_product,
    initialize_database,
    list_products,
    search_products,
)
from src.models import DEFAULT_PRODUCT_STATUS, Product, ProductStatus
from src.validation import TEXT_FIELD_MAX_LENGTHS, validate_product


APP_TITLE: Final[str] = "Product Manager Central"
NAVIGATION_OPTIONS: Final[tuple[str, ...]] = (
    "Dashboard",
    "Create Product",
    "View Products",
    "Search Products",
)


def status_label(status: ProductStatus) -> str:
    """Return a readable label for a canonical product status."""

    return status.value.replace("_", " ").title()


def product_option_label(product: Product) -> str:
    """Return a compact, ID-safe label for a product selector."""

    return f"{product.name} · {status_label(product.status)} · ID {product.id}"


def target_users_summary(target_users: str, limit: int = 90) -> str:
    """Create a compact single-line target-user summary."""

    summary = " ".join(target_users.split())
    if len(summary) <= limit:
        return summary
    return f"{summary[: limit - 1].rstrip()}…"


def display_database_error() -> None:
    """Show a user-safe persistence error without exposing SQL details."""

    st.error(
        "Product data is temporarily unavailable. "
        "Please check the local database and try again."
    )


def display_validation_errors(errors: dict[str, str]) -> None:
    """Display every centralized validation error together."""

    st.error("Please correct the following fields before saving:")
    for message in errors.values():
        st.markdown(f"- {message}")


def display_product_details(product: Product) -> None:
    """Render every canonical field for one saved product."""

    st.subheader(product.name)
    st.caption(f"Product ID {product.id} · {status_label(product.status)}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Description**")
        st.write(product.description)
        st.markdown("**Target users**")
        st.write(product.target_users)
    with right:
        st.markdown("**Business goal**")
        st.write(product.business_goal)
        st.markdown("**Status**")
        st.write(status_label(product.status))

    st.divider()
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


def render_dashboard() -> None:
    """Render the approved product metrics."""

    st.header("Dashboard")
    st.write("A quick overview of your saved product portfolio.")

    try:
        metrics = get_dashboard_metrics()
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    columns = st.columns(4)
    metric_items = (
        ("Total products", metrics["total_products"]),
        ("Active products", metrics["active_products"]),
        ("Launched products", metrics["launched_products"]),
        ("Updated in 30 days", metrics["recently_updated_products"]),
    )
    for column, (label, value) in zip(columns, metric_items, strict=True):
        column.metric(label, value)

    st.caption(
        "Active excludes archived products. Recently updated covers the "
        "previous 30 days."
    )


def render_create_product() -> None:
    """Render the canonical create form and save only validated data."""

    st.header("Create Product")
    st.write(
        "Capture the essential context for a product. "
        "Fields marked with * are required."
    )

    with st.form("create_product_form"):
        name = st.text_input(
            "Name *",
            max_chars=TEXT_FIELD_MAX_LENGTHS["name"],
            help="A clear product name.",
        )
        description = st.text_area(
            "Description *",
            max_chars=TEXT_FIELD_MAX_LENGTHS["description"],
            help="What the product is and what it enables.",
        )
        target_users = st.text_area(
            "Target users *",
            max_chars=TEXT_FIELD_MAX_LENGTHS["target_users"],
            help="The people or groups this product serves.",
        )
        business_goal = st.text_area(
            "Business goal *",
            max_chars=TEXT_FIELD_MAX_LENGTHS["business_goal"],
            help="The business outcome this product should support.",
        )
        status = st.selectbox(
            "Status *",
            options=list(ProductStatus),
            index=list(ProductStatus).index(DEFAULT_PRODUCT_STATUS),
            format_func=status_label,
        )

        st.subheader("Optional context")
        customer_problem = st.text_area(
            "Customer problem",
            max_chars=TEXT_FIELD_MAX_LENGTHS["customer_problem"],
        )
        product_strategy = st.text_area(
            "Product strategy",
            max_chars=TEXT_FIELD_MAX_LENGTHS["product_strategy"],
        )
        notes = st.text_area(
            "Notes",
            max_chars=TEXT_FIELD_MAX_LENGTHS["notes"],
        )

        submitted = st.form_submit_button(
            "Create product",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    product_data = {
        "name": name,
        "description": description,
        "target_users": target_users,
        "business_goal": business_goal,
        "status": status,
        "customer_problem": customer_problem,
        "product_strategy": product_strategy,
        "notes": notes,
    }
    validation_result = validate_product(product_data)
    if not validation_result.is_valid:
        display_validation_errors(validation_result.errors)
        return

    try:
        product = create_product(validation_result.normalized_data)
    except ProductValidationError as error:
        display_validation_errors(error.errors)
        return
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    st.success(f'"{product.name}" was created successfully as product ID {product.id}.')
    st.info("Open View Products to review the complete saved record.")


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
        selected_product = get_product(selected_id)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if selected_product is None:
        st.warning("That product is no longer available. Refresh the page.")
        return

    st.divider()
    display_product_details(selected_product)


def render_view_products() -> None:
    """Render all saved products and allow one to be opened."""

    st.header("View Products")
    st.write("Review your saved products and open a complete product record.")
    try:
        products = list_products()
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    render_product_list(
        products,
        empty_message="No products have been saved yet.",
        selector_key="view_product_selector",
    )


def render_search_products() -> None:
    """Render canonical text search and complete result details."""

    st.header("Search Products")
    st.write("Search names, descriptions, users, goals, and optional context.")
    query = st.text_input(
        "Search",
        placeholder="Enter a name, user, goal, or keyword",
    )

    try:
        products = search_products(query)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if query.strip():
        st.write(
            f"{len(products)} result{'s' if len(products) != 1 else ''} "
            f'for "{query.strip()}"'
        )
        empty_message = "No products match this search."
    else:
        st.caption("Enter a keyword, or browse all products below.")
        empty_message = "No products have been saved yet."

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

    try:
        initialize_database()
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
    )

    st.title(APP_TITLE)
    st.caption("A focused workspace for product strategy and context.")

    renderers: dict[str, Callable[[], None]] = {
        "Dashboard": render_dashboard,
        "Create Product": render_create_product,
        "View Products": render_view_products,
        "Search Products": render_search_products,
    }
    renderers[selected_section]()


if __name__ == "__main__":
    main()
