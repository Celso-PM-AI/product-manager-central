"""Stable BRD and PRD template definitions and product prepopulation."""

from dataclasses import dataclass
from typing import Final

from src.models import DocumentType, Product


@dataclass(frozen=True)
class DocumentSectionDefinition:
    """Persistent key and presentation metadata for one template section."""

    key: str
    label: str
    guidance: str


BRD_SECTIONS: Final[tuple[DocumentSectionDefinition, ...]] = (
    DocumentSectionDefinition(
        "executive_summary",
        "Executive summary",
        "Summarize the business need, proposed direction, and expected value.",
    ),
    DocumentSectionDefinition(
        "business_problem",
        "Business problem",
        "Describe the business problem or opportunity this document addresses.",
    ),
    DocumentSectionDefinition(
        "business_objectives",
        "Business objectives",
        "State the measurable business outcomes the initiative should achieve.",
    ),
    DocumentSectionDefinition(
        "in_scope",
        "In scope",
        "List the capabilities, processes, teams, or outcomes included.",
    ),
    DocumentSectionDefinition(
        "out_of_scope",
        "Out of scope",
        "Clarify what this initiative will not address.",
    ),
    DocumentSectionDefinition(
        "stakeholders",
        "Stakeholders",
        "Identify decision-makers, contributors, affected groups, and approvers.",
    ),
    DocumentSectionDefinition(
        "business_requirements",
        "Business requirements",
        "List the business capabilities and rules required for success.",
    ),
    DocumentSectionDefinition(
        "assumptions_constraints",
        "Assumptions and constraints",
        "Record assumptions, limitations, policies, timelines, or budget constraints.",
    ),
    DocumentSectionDefinition(
        "risks_dependencies",
        "Risks and dependencies",
        "Describe material risks and internal or external dependencies.",
    ),
    DocumentSectionDefinition(
        "success_metrics",
        "Success metrics",
        "Define how business impact and adoption will be measured.",
    ),
    DocumentSectionDefinition(
        "approval_criteria",
        "Approval criteria",
        "State the conditions required for stakeholder approval.",
    ),
)

PRD_SECTIONS: Final[tuple[DocumentSectionDefinition, ...]] = (
    DocumentSectionDefinition(
        "product_overview",
        "Product overview",
        "Summarize the product, its purpose, and the intended value.",
    ),
    DocumentSectionDefinition(
        "customer_problem",
        "Customer problem",
        "Describe the customer need, pain point, or opportunity.",
    ),
    DocumentSectionDefinition(
        "target_users_personas",
        "Target users and personas",
        "Identify primary users, relevant personas, and their context.",
    ),
    DocumentSectionDefinition(
        "product_goals",
        "Product goals",
        "State the outcomes this product or release should achieve.",
    ),
    DocumentSectionDefinition(
        "non_goals",
        "Non-goals",
        "Clarify outcomes and capabilities that are intentionally excluded.",
    ),
    DocumentSectionDefinition(
        "user_stories",
        "User stories",
        "Capture important user needs using concise scenarios or user stories.",
    ),
    DocumentSectionDefinition(
        "functional_requirements",
        "Functional requirements",
        "List the behaviors and capabilities the product must provide.",
    ),
    DocumentSectionDefinition(
        "nonfunctional_requirements",
        "Nonfunctional requirements",
        "Describe performance, reliability, accessibility, scalability, and operational needs.",
    ),
    DocumentSectionDefinition(
        "user_experience_requirements",
        "User experience requirements",
        "Describe essential workflows, usability expectations, and interaction constraints.",
    ),
    DocumentSectionDefinition(
        "data_security_privacy_requirements",
        "Data, security, and privacy requirements",
        "Record data handling, security controls, privacy obligations, and compliance needs.",
    ),
    DocumentSectionDefinition(
        "dependencies_risks",
        "Dependencies and risks",
        "Identify delivery dependencies, assumptions, and material product risks.",
    ),
    DocumentSectionDefinition(
        "success_metrics",
        "Success metrics",
        "Define product, customer, and business measures of success.",
    ),
    DocumentSectionDefinition(
        "acceptance_criteria",
        "Acceptance criteria",
        "State the verifiable conditions required for the product to be accepted.",
    ),
    DocumentSectionDefinition(
        "release_considerations",
        "Release considerations",
        "Describe rollout, migration, enablement, support, and monitoring needs.",
    ),
)

DOCUMENT_TEMPLATES: Final[dict[DocumentType, tuple[DocumentSectionDefinition, ...]]] = {
    DocumentType.BRD: BRD_SECTIONS,
    DocumentType.PRD: PRD_SECTIONS,
}


def document_template(document_type: DocumentType) -> tuple[DocumentSectionDefinition, ...]:
    """Return the ordered, stable section definitions for a document type."""

    return DOCUMENT_TEMPLATES[document_type]


def derived_document_title(product: Product, document_type: DocumentType) -> str:
    """Create the editable starting title for a new document."""

    return f"{product.name} {document_type.value}"


def prepopulated_sections(
    product: Product,
    document_type: DocumentType,
) -> dict[str, str]:
    """Create a one-time section snapshot from high-confidence product fields."""

    sections = {section.key: "" for section in document_template(document_type)}
    if document_type is DocumentType.BRD:
        sections.update(
            executive_summary=product.description,
            business_problem=product.customer_problem or "",
            business_objectives=product.business_goal,
        )
    else:
        sections.update(
            product_overview=product.description,
            customer_problem=product.customer_problem or "",
            target_users_personas=product.target_users,
            product_goals=product.business_goal,
        )
    return sections
