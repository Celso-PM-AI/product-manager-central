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
    group: str


BRD_SECTIONS: Final[tuple[DocumentSectionDefinition, ...]] = (
    DocumentSectionDefinition(
        "executive_summary",
        "Executive summary",
        "Summarize the business need, proposed direction, and expected value.",
        "1. Executive Summary and Project Overview",
    ),
    DocumentSectionDefinition("project_purpose_vision", "Project purpose and vision", "Describe the intended business change and long-term vision.", "1. Executive Summary and Project Overview"),
    DocumentSectionDefinition("strategic_alignment", "Strategic alignment", "Explain how the initiative supports organizational strategy.", "1. Executive Summary and Project Overview"),
    DocumentSectionDefinition(
        "business_problem",
        "Business problem or opportunity",
        "Describe the business problem or opportunity this document addresses.",
        "2. Business Objectives and Goals",
    ),
    DocumentSectionDefinition(
        "business_objectives",
        "Business goals",
        "State the measurable business outcomes the initiative should achieve.",
        "2. Business Objectives and Goals",
    ),
    DocumentSectionDefinition("quantifiable_success_criteria", "Quantifiable success criteria", "Define measurable criteria for business success.", "2. Business Objectives and Goals"),
    DocumentSectionDefinition(
        "in_scope",
        "In scope",
        "List the capabilities, processes, teams, or outcomes included.",
        "3. Project Scope",
    ),
    DocumentSectionDefinition(
        "out_of_scope",
        "Out of scope",
        "Clarify what this initiative will not address.",
        "3. Project Scope",
    ),
    DocumentSectionDefinition(
        "stakeholders",
        "Stakeholder analysis",
        "Identify decision-makers, contributors, affected groups, and approvers.",
        "4. Stakeholders and Business Context",
    ),
    DocumentSectionDefinition("current_state", "Current state", "Describe today's processes, systems, and business conditions.", "4. Stakeholders and Business Context"),
    DocumentSectionDefinition("future_state", "Future state", "Describe the intended future business condition.", "4. Stakeholders and Business Context"),
    DocumentSectionDefinition(
        "business_requirements",
        "Functional business requirements",
        "List the business capabilities and rules required for success.",
        "5. Business Requirements",
    ),
    DocumentSectionDefinition("data_reporting_requirements", "Data and reporting requirements", "Describe required business data, reports, and decision support.", "5. Business Requirements"),
    DocumentSectionDefinition("epics", "Epics", "List the major business outcome groupings.", "5. Business Requirements"),
    DocumentSectionDefinition("capabilities", "Capabilities", "List the business capabilities needed to deliver the outcomes.", "5. Business Requirements"),
    DocumentSectionDefinition("features", "Features", "List the business-facing features in scope.", "5. Business Requirements"),
    DocumentSectionDefinition("user_stories", "User stories", "Capture business user needs as concise stories.", "5. Business Requirements"),
    DocumentSectionDefinition("acceptance_criteria", "Associated acceptance criteria", "State testable criteria associated with the business stories or requirements.", "5. Business Requirements"),
    DocumentSectionDefinition("regulatory_compliance", "Regulatory and compliance requirements", "Record applicable laws, regulations, policies, and audit needs.", "6. Nonfunctional and Operational Requirements"),
    DocumentSectionDefinition("security_access_control", "Security and access control", "Define business access, authorization, and protection needs.", "6. Nonfunctional and Operational Requirements"),
    DocumentSectionDefinition("business_continuity", "Business continuity", "Describe continuity, recovery, and resilience expectations.", "6. Nonfunctional and Operational Requirements"),
    DocumentSectionDefinition("service_level_requirements", "Service-level requirements", "Define measurable service expectations.", "6. Nonfunctional and Operational Requirements"),
    DocumentSectionDefinition(
        "assumptions_constraints",
        "Assumptions and constraints",
        "Record assumptions, limitations, policies, timelines, or budget constraints.",
        "7. Constraints, Assumptions, and Dependencies",
    ),
    DocumentSectionDefinition(
        "risks_dependencies",
        "Risks and dependencies",
        "Describe material risks and internal or external dependencies.",
        "7. Constraints, Assumptions, and Dependencies",
    ),
    DocumentSectionDefinition("roi_financial_justification", "ROI and financial justification", "Explain expected return and the financial basis for investment.", "8. Cost-Benefit Analysis and Financial Impact"),
    DocumentSectionDefinition("implementation_costs_benefits", "Implementation costs and expected benefits", "Describe material costs and expected benefits.", "8. Cost-Benefit Analysis and Financial Impact"),
    DocumentSectionDefinition("resource_allocation", "Resource allocation", "Describe people, funding, and capacity needs.", "8. Cost-Benefit Analysis and Financial Impact"),
    DocumentSectionDefinition("business_risks", "Business risks", "Identify material business risks.", "9. Risk Assessment and Management"),
    DocumentSectionDefinition("risk_impact", "Risk impact", "Assess likely impact and exposure.", "9. Risk Assessment and Management"),
    DocumentSectionDefinition("mitigation_strategies", "Mitigation strategies", "Define owners and actions that reduce risk.", "9. Risk Assessment and Management"),
    DocumentSectionDefinition(
        "success_metrics",
        "Supporting success metrics",
        "Define how business impact and adoption will be measured.",
        "9. Risk Assessment and Management",
    ),
    DocumentSectionDefinition(
        "approval_criteria",
        "Approval criteria",
        "State the conditions required for stakeholder approval.",
        "9. Risk Assessment and Management",
    ),
)

PRD_SECTIONS: Final[tuple[DocumentSectionDefinition, ...]] = (
    DocumentSectionDefinition(
        "product_overview",
        "Product overview",
        "Summarize the product, its purpose, and the intended value.",
        "1. Document Overview and Metadata",
    ),
    DocumentSectionDefinition("contributors_roles", "Contributors and roles", "Identify document contributors, reviewers, approvers, and their roles.", "1. Document Overview and Metadata"),
    DocumentSectionDefinition(
        "customer_problem",
        "Problem statement",
        "Describe the customer need, pain point, or opportunity.",
        "2. Purpose and Objective",
    ),
    DocumentSectionDefinition(
        "target_users_personas",
        "Target audience",
        "Identify primary users, relevant personas, and their context.",
        "2. Purpose and Objective",
    ),
    DocumentSectionDefinition(
        "product_goals",
        "Business goals",
        "State the outcomes this product or release should achieve.",
        "2. Purpose and Objective",
    ),
    DocumentSectionDefinition("in_scope", "In scope", "List the product behaviors, users, and release outcomes included.", "3. Scope and Release Strategy"),
    DocumentSectionDefinition(
        "non_goals",
        "Out of scope",
        "Clarify outcomes and capabilities that are intentionally excluded.",
        "3. Scope and Release Strategy",
    ),
    DocumentSectionDefinition(
        "user_stories",
        "User stories",
        "Capture important user needs using concise scenarios or user stories.",
        "4. Functional Requirements",
    ),
    DocumentSectionDefinition(
        "functional_requirements",
        "Functional requirements",
        "List the behaviors and capabilities the product must provide.",
        "4. Functional Requirements",
    ),
    DocumentSectionDefinition("acceptance_criteria", "Acceptance criteria", "State testable conditions for the functional requirements and user stories.", "4. Functional Requirements"),
    DocumentSectionDefinition("feature_list_prioritization", "Feature list and prioritization", "List features and their approved priority.", "4. Functional Requirements"),
    DocumentSectionDefinition("workflows", "Workflows", "Describe essential end-to-end product workflows.", "4. Functional Requirements"),
    DocumentSectionDefinition("edge_cases_error_scenarios", "Edge cases and error scenarios", "Describe boundary, failure, and recovery behavior.", "4. Functional Requirements"),
    DocumentSectionDefinition(
        "nonfunctional_requirements",
        "Nonfunctional requirements",
        "Describe performance, reliability, accessibility, scalability, and operational needs.",
        "5. Nonfunctional Requirements",
    ),
    DocumentSectionDefinition("performance", "Performance", "Define measurable performance expectations.", "5. Nonfunctional Requirements"),
    DocumentSectionDefinition("security_privacy", "Security and privacy", "Define security, privacy, and data-protection behavior.", "5. Nonfunctional Requirements"),
    DocumentSectionDefinition("scalability_reliability", "Scalability and reliability", "Define capacity, availability, resilience, and recovery expectations.", "5. Nonfunctional Requirements"),
    DocumentSectionDefinition("accessibility", "Accessibility", "Define applicable accessibility standards and measurable outcomes.", "5. Nonfunctional Requirements"),
    DocumentSectionDefinition(
        "user_experience_requirements",
        "User experience requirements",
        "Describe essential workflows, usability expectations, and interaction constraints.",
        "6. Design and User Experience",
    ),
    DocumentSectionDefinition(
        "data_security_privacy_requirements",
        "Data, security, and privacy requirements",
        "Record data handling, security controls, privacy obligations, and compliance needs.",
        "5. Nonfunctional Requirements",
    ),
    DocumentSectionDefinition("wireframes_mockups", "Wireframes and mockups", "Describe or reference approved interface concepts.", "6. Design and User Experience"),
    DocumentSectionDefinition("user_flow_diagrams", "User-flow diagrams", "Describe or reference approved end-to-end user flows.", "6. Design and User Experience"),
    DocumentSectionDefinition("design_references_links", "Design references or links", "Record durable design references without secrets.", "6. Design and User Experience"),
    DocumentSectionDefinition(
        "dependencies_risks",
        "Dependencies and risks",
        "Identify delivery dependencies, assumptions, and material product risks.",
        "8. Assumptions, Constraints, and Dependencies",
    ),
    DocumentSectionDefinition(
        "success_metrics",
        "Key success metrics",
        "Define product, customer, and business measures of success.",
        "7. Success Metrics and KPIs",
    ),
    DocumentSectionDefinition(
        "tracking_strategy", "Tracking strategy",
        "Explain how, where, and how frequently product performance will be monitored. Example: Track scheduling starts, completions, abandonment, errors, and appointment outcomes through product analytics dashboards. Review weekly during beta and monthly after launch.",
        "7. Success Metrics and KPIs",
    ),
    DocumentSectionDefinition(
        "analytics_telemetry", "Analytics events or telemetry",
        "List the specific product events, signals, or logs required for measurement. Examples: scheduling_started, availability_viewed, appointment_selected, appointment_confirmed, appointment_rescheduled, appointment_cancelled, scheduling_failed. Examples are guidance only and are not saved automatically.",
        "7. Success Metrics and KPIs",
    ),
    DocumentSectionDefinition("assumptions", "Assumptions", "Record assumptions that affect scope or validation.", "8. Assumptions, Constraints, and Dependencies"),
    DocumentSectionDefinition("constraints", "Constraints", "Record product, delivery, policy, or technology constraints.", "8. Assumptions, Constraints, and Dependencies"),
    DocumentSectionDefinition("dependencies", "Dependencies", "Record internal and external dependencies.", "8. Assumptions, Constraints, and Dependencies"),
    DocumentSectionDefinition("measurable_quality_thresholds", "Measurable product-behavior and quality thresholds", "Express grounding or quality needs as measurable product outcomes, not internal model controls.", "8. Assumptions, Constraints, and Dependencies"),
    DocumentSectionDefinition("key_dates", "Key dates", "Record important target dates and review windows.", "9. Timeline, Milestones, and Open Questions"),
    DocumentSectionDefinition("milestones", "Milestones", "List ordered delivery and validation milestones.", "9. Timeline, Milestones, and Open Questions"),
    DocumentSectionDefinition("open_questions", "Open questions", "Record unresolved product decisions without inventing answers.", "9. Timeline, Milestones, and Open Questions"),
    DocumentSectionDefinition("decision_owners", "Decision owners", "Identify accountable owners for open decisions.", "9. Timeline, Milestones, and Open Questions"),
    DocumentSectionDefinition(
        "release_considerations",
        "Release considerations",
        "Describe rollout, migration, enablement, support, and monitoring needs.",
        "9. Timeline, Milestones, and Open Questions",
    ),
)

DOCUMENT_TEMPLATES: Final[dict[DocumentType, tuple[DocumentSectionDefinition, ...]]] = {
    DocumentType.BRD: BRD_SECTIONS,
    DocumentType.PRD: PRD_SECTIONS,
}


def document_template(document_type: DocumentType) -> tuple[DocumentSectionDefinition, ...]:
    """Return the ordered, stable section definitions for a document type."""

    return tuple(
        sorted(
            DOCUMENT_TEMPLATES[document_type],
            key=lambda definition: int(definition.group.split(".", 1)[0]),
        )
    )


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
