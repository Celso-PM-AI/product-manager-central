"""Optional, deterministic fictional data for first-time PMC exploration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from src.database import (
    DATABASE_FILE,
    create_document,
    create_product,
    list_documents_for_product,
    list_products,
    update_product,
)
from src.document_templates import document_template
from src.models import DocumentStatus, DocumentType, Product


SAMPLE_ID: Final[str] = "pmc-fictional-trailwise-v1"
SAMPLE_PRODUCT_NAME: Final[str] = "[Fictional Sample] Trailwise"
SAMPLE_APPROVED_PRD_TITLE: Final[str] = (
    "[Fictional Sample] Trailwise Guided Planning PRD"
)
SAMPLE_DRAFT_BRD_TITLE: Final[str] = (
    "[Fictional Sample] Trailwise Expansion BRD"
)
SAMPLE_LOADING_NOTE: Final[str] = (
    f"Fictional PMC onboarding data. Sample ID: {SAMPLE_ID}. Loading is in "
    "progress; it is safe to retry from Getting Started."
)
SAMPLE_READY_NOTE: Final[str] = (
    f"Fictional PMC onboarding data. Sample ID: {SAMPLE_ID}. Find this product "
    "in View Products and use Delete if you want to remove the sample and its "
    "documents."
)


class SampleDataLoadStatus(str, Enum):
    """Outcomes of an explicit sample-data request."""

    CREATED = "created"
    ALREADY_LOADED = "already_loaded"


@dataclass(frozen=True)
class SampleDataLoadResult:
    """Safe, non-sensitive result for the onboarding interface."""

    status: SampleDataLoadStatus
    product: Product


def _sample_sections(
    document_type: DocumentType,
    content_by_key: dict[str, str],
) -> dict[str, str]:
    return {
        definition.key: content_by_key.get(
            definition.key,
            (
                "Fictional planning content for the Trailwise sample. This "
                "section is included only to demonstrate PMC document structure."
            ),
        )
        for definition in document_template(document_type)
    }


def _approved_prd_data(product_id: int) -> dict[str, object]:
    return {
        "product_id": product_id,
        "document_type": DocumentType.PRD,
        "title": SAMPLE_APPROVED_PRD_TITLE,
        "version": "1.0",
        "document_status": DocumentStatus.APPROVED,
        "sections": _sample_sections(
            DocumentType.PRD,
            {
                "product_overview": (
                    "Trailwise is a fictional local planning companion that helps "
                    "community hiking groups prepare accessible day trips."
                ),
                "customer_problem": (
                    "Volunteer trip leaders spend too much time reconciling route "
                    "difficulty, accessibility needs, weather plans, and equipment."
                ),
                "target_users_personas": (
                    "Primary users are fictional volunteer trip leaders and group "
                    "coordinators planning inclusive local outings."
                ),
                "product_goals": (
                    "Reduce planning time and make route constraints visible before "
                    "a group confirms an outing."
                ),
                "non_goals": (
                    "Trailwise does not provide emergency response, medical advice, "
                    "or real-time navigation."
                ),
                "user_stories": (
                    "As a trip leader, I want one readiness summary so that I can "
                    "review route and participant needs with the group."
                ),
                "functional_requirements": (
                    "Users can record route details, accessibility considerations, "
                    "equipment needs, and a weather contingency."
                ),
                "nonfunctional_requirements": (
                    "The fictional prototype should preserve saved plans locally "
                    "and present essential information in plain language."
                ),
                "user_experience_requirements": (
                    "A trip leader should be able to review a concise readiness "
                    "summary without learning specialist planning terminology."
                ),
                "data_security_privacy_requirements": (
                    "The sample uses no real participant data. Users should avoid "
                    "entering medical or other sensitive personal information."
                ),
                "dependencies_risks": (
                    "Route conditions may change, so leaders must verify information "
                    "with authoritative local sources before an outing."
                ),
                "success_metrics": (
                    "A fictional beta target is a 30 percent reduction in planning "
                    "time with every outing receiving a human readiness review."
                ),
                "acceptance_criteria": (
                    "A saved plan identifies route constraints, equipment, a weather "
                    "contingency, and the person responsible for final review."
                ),
                "release_considerations": (
                    "Begin with a small fictional pilot and collect usability feedback "
                    "before expanding the planning template."
                ),
            },
        ),
    }


def _draft_brd_data(product_id: int) -> dict[str, object]:
    return {
        "product_id": product_id,
        "document_type": DocumentType.BRD,
        "title": SAMPLE_DRAFT_BRD_TITLE,
        "version": "0.1",
        "document_status": DocumentStatus.DRAFT,
        "sections": _sample_sections(
            DocumentType.BRD,
            {
                "executive_summary": (
                    "Fictional early thinking about offering Trailwise templates to "
                    "community garden volunteer teams."
                ),
                "business_problem": (
                    "The opportunity and user need have not yet been validated."
                ),
                "business_objectives": (
                    "Explore whether the planning approach transfers to another "
                    "volunteer setting before making an investment decision."
                ),
                "approval_criteria": (
                    "Keep this document in Draft until a human reviewer validates the "
                    "problem, scope, stakeholders, and evidence."
                ),
            },
        ),
    }


def _sample_product_data(notes: str) -> dict[str, object]:
    return {
        "name": SAMPLE_PRODUCT_NAME,
        "description": (
            "A fictional planning workspace for inclusive community hiking trips."
        ),
        "target_users": "Fictional volunteer trip leaders and group coordinators",
        "business_goal": (
            "Demonstrate PMC product, document, trusted-source, and citation workflows."
        ),
        "status": "planning",
        "customer_problem": (
            "Trip-planning details are scattered across messages and checklists."
        ),
        "product_strategy": (
            "Start with a simple readiness template and validate it with fictional "
            "community-outing scenarios."
        ),
        "notes": notes,
    }


def _find_sample_product(database_path: str | Path) -> Product | None:
    for product in list_products(database_path):
        if product.notes in {SAMPLE_LOADING_NOTE, SAMPLE_READY_NOTE}:
            return product
    return None


def load_fictional_sample_data(
    database_path: str | Path = DATABASE_FILE,
) -> SampleDataLoadResult:
    """Create the fictional sample only after an explicit, repeat-safe request."""

    product = _find_sample_product(database_path)
    if product is not None and product.notes == SAMPLE_READY_NOTE:
        return SampleDataLoadResult(SampleDataLoadStatus.ALREADY_LOADED, product)

    if product is None:
        product = create_product(
            _sample_product_data(SAMPLE_LOADING_NOTE),
            database_path,
        )
    if product.id is None:
        raise RuntimeError("The fictional sample product could not be identified.")

    existing_documents = {
        (document.document_type, document.title)
        for document in list_documents_for_product(product.id, database_path)
    }
    sample_documents = (
        (DocumentType.PRD, SAMPLE_APPROVED_PRD_TITLE, _approved_prd_data),
        (DocumentType.BRD, SAMPLE_DRAFT_BRD_TITLE, _draft_brd_data),
    )
    for document_type, title, factory in sample_documents:
        if (document_type, title) not in existing_documents:
            create_document(factory(product.id), database_path)

    ready_product = update_product(
        product.id,
        _sample_product_data(SAMPLE_READY_NOTE),
        database_path,
    )
    if ready_product is None:
        raise RuntimeError("The fictional sample product is no longer available.")
    return SampleDataLoadResult(SampleDataLoadStatus.CREATED, ready_product)
