"""Streamlit interface for Product Manager Central."""

import os
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

import streamlit as st

from src.agile import AgileArtifactType, AgileReviewState, PARENT_TYPE
from src.agile_generation import (
    AgileGenerationError,
    AgileGenerationRequest,
    AgileGenerationState,
    AgileParentContext,
    GroundedAgileGenerationService,
    SourceScopedAgileRetriever,
)
from src.agile_profiles import AGILE_PROFILE_DEFINITIONS, DEFAULT_AGILE_PROFILE
from src.agile_prompt_catalog import AgilePromptTask, get_agile_prompt
from src.agile_review import AgileReviewBatch, AgileReviewError, AgileReviewService

from src.ai_service import (
    AIConfigurationError,
    AIServiceError,
    OpenAIService,
    get_ai_configuration,
)
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
    list_accepted_agile_batches_for_product,
    list_generated_artifacts_for_product,
    list_products,
    list_retrievable_document_sections,
    search_products,
    update_document,
    update_product,
)
from src.document_templates import (
    derived_document_title,
    document_template,
    prepopulated_sections,
)
from src.document_export import (
    DocumentExportError,
    ExportFormat,
    create_document_export,
)
from src.grounded_generation import (
    DatabaseGroundedGenerationService,
    GenerationRequestError,
    normalize_generation_request,
)
from src.generated_content import (
    GeneratedContentReview,
    GeneratedContentReviewService,
    ReviewDecision,
    ReviewValidationError,
)
from src.models import (
    DEFAULT_PRODUCT_STATUS,
    DocumentStatus,
    DocumentType,
    Product,
    ProductDocument,
    ProductStatus,
    SuccessMatrixStatus,
)
from src.model_controls import ModelCapabilities, RetrievalControls
from src.prompt_catalog import (
    AssistantTask,
    PromptCatalogError,
    approved_prompts_for_task,
    assistant_task_label,
    get_approved_prompt,
)
from src.sample_data import (
    SAMPLE_PRODUCT_NAME,
    SampleDataLoadStatus,
    load_fictional_sample_data,
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
    "AI Assistant",
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
GENERATED_REVIEW_STATE_KEY: Final[str] = "generated_content_review"
GENERATION_SUBMISSION_STATE_KEY: Final[str] = "grounded_generation_submission"
AGILE_REVIEW_STATE_KEY: Final[str] = "agile_review_batch"
AGILE_SUBMISSION_STATE_KEY: Final[str] = "agile_generation_submission"
LAST_NAVIGATION_KEY: Final[str] = "_last_navigation_section"


def display_generation_citations(review: GeneratedContentReview) -> None:
    """Render immutable supporting citations for a generated-content review."""

    st.markdown("### Supporting source citations")
    for citation in review.citations:
        st.markdown(
            f"**[Source {citation.source_number}]** "
            f"{citation.product} (product ID {citation.product_id}) · "
            f"{citation.document_title} (document ID {citation.document_id}) · "
            f"{citation.document_type.value} · {citation.section}"
        )


def render_generated_content_review(review: GeneratedContentReview) -> None:
    """Render pending, rejected, or accepted human-review state."""

    service = GeneratedContentReviewService(APP_DATABASE_FILE)
    st.subheader("Original AI output")
    st.warning(
        "AI-generated content — review carefully. It is separate from every "
        "original BRD and PRD."
    )
    st.markdown(review.original_content)
    display_generation_citations(review)

    if review.was_revised:
        st.markdown("### Human-revised content")
        st.markdown(review.content_for_acceptance)

    if review.decision is ReviewDecision.REJECTED:
        st.warning(
            "Generated content was rejected. It was not saved as an approved "
            "product artifact, and no source document was changed."
        )
        return
    if review.decision is ReviewDecision.ACCEPTED:
        st.success(
            "Generated content was explicitly accepted and saved separately "
            f"as artifact ID {review.saved_artifact_id}."
        )
        return

    st.info(
        "This review is pending. Applying a revision does not save it; you must "
        "still choose Accept and save."
    )
    with st.form("generated_content_revision_form"):
        revised_content = st.text_area(
            "Revise generated content before acceptance",
            value=review.content_for_acceptance,
            max_chars=50_000,
            key=f"generated_content_revision_{review.review_key}",
        )
        apply_revision = st.form_submit_button("Apply revision")
    if apply_revision:
        try:
            st.session_state[GENERATED_REVIEW_STATE_KEY] = service.revise(
                review,
                revised_content,
            )
        except ReviewValidationError as error:
            st.error(str(error))
            return
        st.success(
            "Revision applied for review. It is still unaccepted and unsaved."
        )
        st.rerun()

    accept_column, reject_column = st.columns(2)
    accept = accept_column.button(
        "Accept and save",
        type="primary",
        width="stretch",
        key=f"accept_generated_content_{review.review_key}",
    )
    reject = reject_column.button(
        "Reject",
        width="stretch",
        key=f"reject_generated_content_{review.review_key}",
    )
    if reject:
        try:
            st.session_state[GENERATED_REVIEW_STATE_KEY] = service.reject(review)
        except ReviewValidationError as error:
            st.error(str(error))
            return
        st.rerun()
    if not accept:
        return
    try:
        accepted = service.accept(review)
    except ReviewValidationError as error:
        st.error(str(error))
        return
    except (DatabaseSchemaError, sqlite3.Error):
        st.error(
            "Accepted content could not be saved safely. Please try again."
        )
        return
    st.session_state[GENERATED_REVIEW_STATE_KEY] = accepted.review
    st.rerun()


def render_general_assistant() -> None:
    """Render the original grounded-draft workflow."""

    st.subheader("General grounded draft")
    st.caption(
        "Generate a temporary draft grounded only in Approved BRDs and PRDs. "
        "Draft documents are excluded."
    )
    configuration = get_ai_configuration()
    if configuration.configured:
        st.info(configuration.status_message)
    else:
        st.warning(configuration.status_message)

    try:
        products = list_products(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return

    if not products:
        st.info(
            "No products are available. Create a product before generating and "
            "reviewing content."
        )
        return

    products_by_id = {
        product.id: product for product in products if product.id is not None
    }
    product_id = st.selectbox(
        "Product for the generated artifact",
        options=[None, *products_by_id],
        format_func=lambda selected: (
            "Select a product"
            if selected is None
            else product_option_label(products_by_id[selected])
        ),
        key="grounded_generation_product_id",
    )
    task = st.selectbox(
        "Assistant task",
        options=[None, *AssistantTask],
        format_func=lambda selected: (
            "Select an assistant task"
            if selected is None
            else assistant_task_label(selected)
        ),
        key="grounded_generation_task",
    )
    available_prompts = approved_prompts_for_task(task) if task is not None else ()
    prompts_by_id = {prompt.prompt_id: prompt for prompt in available_prompts}
    prompt_id = st.selectbox(
        "Approved prompt",
        options=[None, *prompts_by_id],
        format_func=lambda selected: (
            "Select an approved prompt"
            if selected is None
            else prompts_by_id[selected].name
        ),
        key="grounded_generation_prompt_id",
    )
    if prompt_id is not None:
        selected_prompt = prompts_by_id[prompt_id]
        st.markdown(f"**{selected_prompt.name}**")
        st.caption(selected_prompt.description)
        st.caption(f"Prompt version {selected_prompt.version}")

    with st.form("grounded_generation_form"):
        request = st.text_area(
            "What would you like to draft?",
            placeholder=(
                "For example: Draft a launch-readiness summary using the approved "
                "product requirements."
            ),
            max_chars=10_000,
            key="grounded_generation_request",
        )
        generate = st.form_submit_button("Generate draft", type="primary")

    if not generate:
        review = st.session_state.get(GENERATED_REVIEW_STATE_KEY)
        if isinstance(review, GeneratedContentReview):
            render_generated_content_review(review)
        else:
            st.info(
                "Nothing is saved automatically. Generate content, review its "
                "citations, then explicitly accept or reject it."
            )
        return

    try:
        if product_id is None:
            st.error("Select a product before generating content for review.")
            return
        normalized_request = normalize_generation_request(request)
        selected_prompt = get_approved_prompt(task, prompt_id)
    except (GenerationRequestError, PromptCatalogError) as error:
        st.error(str(error))
        return

    submission_signature = (
        product_id,
        selected_prompt.task.value,
        selected_prompt.prompt_id,
        normalized_request,
    )
    previous_submission = st.session_state.get(GENERATION_SUBMISSION_STATE_KEY)
    existing_review = st.session_state.get(GENERATED_REVIEW_STATE_KEY)
    if (
        isinstance(previous_submission, dict)
        and previous_submission.get("signature") == submission_signature
        and previous_submission.get("status") in {"processing", "completed"}
        and isinstance(existing_review, GeneratedContentReview)
    ):
        st.info(
            "This assistant submission was already processed. The existing "
            "review is shown below; no duplicate generation was started."
        )
        render_generated_content_review(existing_review)
        return

    st.session_state[GENERATION_SUBMISSION_STATE_KEY] = {
        "signature": submission_signature,
        "status": "processing",
    }
    try:
        ai_service = OpenAIService.from_environment()
        result = DatabaseGroundedGenerationService(
            ai_service,
            APP_DATABASE_FILE,
        ).generate(
            normalized_request,
            task=selected_prompt.task,
            prompt_id=selected_prompt.prompt_id,
        )
    except AIConfigurationError as error:
        st.session_state.pop(GENERATION_SUBMISSION_STATE_KEY, None)
        st.error(str(error))
        return
    except AIServiceError as error:
        st.session_state.pop(GENERATION_SUBMISSION_STATE_KEY, None)
        st.error(str(error))
        return
    except (ValueError, DatabaseSchemaError, sqlite3.Error):
        st.session_state.pop(GENERATION_SUBMISSION_STATE_KEY, None)
        st.error(
            "A grounded draft could not be generated safely. Please check the "
            "request and try again."
        )
        return

    if not result.grounded:
        st.session_state.pop(GENERATION_SUBMISSION_STATE_KEY, None)
        st.warning(result.message)
        return
    try:
        review = GeneratedContentReviewService(APP_DATABASE_FILE).begin_review(
            product_id=product_id,
            request=request,
            generation=result,
        )
    except ReviewValidationError as error:
        st.error(str(error))
        return
    st.session_state[GENERATED_REVIEW_STATE_KEY] = review
    st.session_state[GENERATION_SUBMISSION_STATE_KEY] = {
        "signature": submission_signature,
        "status": "completed",
    }
    render_generated_content_review(review)


AGILE_TYPE_OPTIONS: Final[tuple[tuple[str, AgilePromptTask, AgileArtifactType], ...]] = (
    ("Epic", AgilePromptTask.GENERATE_EPIC, AgileArtifactType.EPIC),
    ("Capability", AgilePromptTask.GENERATE_CAPABILITY, AgileArtifactType.CAPABILITY),
    ("Feature", AgilePromptTask.GENERATE_FEATURE, AgileArtifactType.FEATURE),
    ("User Story", AgilePromptTask.GENERATE_USER_STORY, AgileArtifactType.USER_STORY),
    (
        "Structured acceptance criteria",
        AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA,
        AgileArtifactType.USER_STORY,
    ),
)


def _agile_runtime() -> tuple[SourceScopedAgileRetriever, OpenAIService]:
    ai_service = OpenAIService.from_environment()
    retriever = SourceScopedAgileRetriever(
        lambda: list_retrievable_document_sections(APP_DATABASE_FILE),
        ai_service,
    )
    return retriever, ai_service


class _ReviewOnlyEmbeddingProvider:
    """Guard against accidentally performing retrieval during review actions."""

    def create_embeddings(self, texts: list[str]) -> list[tuple[float, ...]]:
        raise RuntimeError("Review revalidation must not request new embeddings.")


def _agile_review_retriever() -> SourceScopedAgileRetriever:
    """Build the read-only revalidator without requiring provider credentials."""

    return SourceScopedAgileRetriever(
        lambda: list_retrievable_document_sections(APP_DATABASE_FILE),
        _ReviewOnlyEmbeddingProvider(),
    )


def _display_agile_sources(sources: tuple[object, ...]) -> None:
    for source in sources:
        st.markdown(
            f"- `{source.reference_id}` — {source.document_title} "
            f"(document ID {source.document_id}) · {source.document_type.value} · "
            f"{source.section_title}"
        )


def render_agile_review(review: AgileReviewBatch) -> None:
    """Show structured output, traceability, gates, and explicit review actions."""

    st.divider()
    st.subheader("Agile generation review")
    st.caption(
        f"Review {review.review_id} · revision {review.revision} · "
        f"{review.review_state.value.replace('_', ' ').title()} · "
        f"prompt {review.request.prompt_id} v{review.request.prompt_version} · "
        f"profile {review.original_generation.profile.value.replace('_', ' ').title()} · "
        f"retrieval Top-K {review.request.retrieval_controls.top_k}"
    )
    st.warning(
        "Generated content is temporary until explicit acceptance. Revisions are "
        "re-grounded and reassessed; source documents are never changed."
    )

    for artifact in review.artifacts:
        with st.expander(
            f"{artifact.position}. {artifact.artifact_type.value.replace('_', ' ').title()}: {artifact.title}",
            expanded=True,
        ):
            st.markdown("**Description**")
            st.write(artifact.description)
            if artifact.parent_artifact_id:
                st.markdown(f"**Parent artifact:** `{artifact.parent_artifact_id}`")
            st.markdown("**Artifact-level citations**")
            _display_agile_sources(artifact.source_references)
            st.markdown("**Structured acceptance criteria**")
            for criterion in artifact.acceptance_criteria:
                st.markdown(
                    f"{criterion.position}. {criterion.text} "
                    f"(`{criterion.criterion_id}`)"
                )
                _display_agile_sources(criterion.source_references)

    st.markdown("### Claim-support results")
    for assessment in review.assessments:
        display = st.success if assessment.supported else st.error
        display(
            f"{assessment.claim.location}: {assessment.outcome.value} "
            f"({assessment.reason.value}) · claim {assessment.claim.claim_id}"
        )
    if review.missing_requirements:
        st.error("Unresolved source gaps block acceptance.")
        for requirement in review.missing_requirements:
            st.write(f"- {requirement.requirement_id}: {requirement.description}")
    if review.proposals:
        st.error("Non-saveable proposals block acceptance.")
        for proposal in review.proposals:
            st.write(f"- {proposal.proposal_id}: {proposal.text}")

    st.markdown("### Fail-closed acceptance gates")
    for gate in review.gates:
        if gate.passed:
            st.success(f"{gate.gate_id.replace('_', ' ').title()}: passed")
        else:
            st.error(f"{gate.gate_id.replace('_', ' ').title()}: blocked")
            for reason in gate.reasons:
                st.write(f"- {reason.code.value}: {reason.message}")

    if review.review_state is AgileReviewState.REJECTED:
        st.warning("This review was rejected and did not enter accepted storage.")
        return
    if review.review_state is AgileReviewState.ACCEPTED:
        st.success(
            f"Accepted batch {review.accepted_batch.batch_id} is stored separately "
            "from its BRD/PRD sources."
        )
        return

    with st.form(f"agile_revision_form_{review.review_id}_{review.revision}"):
        revised_artifacts = []
        for artifact in review.artifacts:
            title = st.text_input(
                f"Revise title · {artifact.artifact_id}",
                value=artifact.title,
                key=f"agile_revision_title_{review.review_id}_{review.revision}_{artifact.artifact_id}",
            )
            description = st.text_area(
                f"Revise description · {artifact.artifact_id}",
                value=artifact.description,
                key=f"agile_revision_description_{review.review_id}_{review.revision}_{artifact.artifact_id}",
            )
            criteria = tuple(
                replace(
                    criterion,
                    text=st.text_area(
                        f"Revise criterion · {criterion.criterion_id}",
                        value=criterion.text,
                        key=f"agile_revision_criterion_{review.review_id}_{review.revision}_{criterion.criterion_id}",
                    ),
                )
                for criterion in artifact.acceptance_criteria
            )
            revised_artifacts.append(
                replace(artifact, title=title, description=description, acceptance_criteria=criteria)
            )
        reviewer = st.text_input(
            "Reviewer identity *",
            value="Product Manager",
            key=f"agile_reviewer_{review.review_id}_{review.revision}",
        )
        revise = st.form_submit_button("Revise and reassess")
    if revise:
        try:
            revised_review = AgileReviewService(
                _agile_review_retriever(), APP_DATABASE_FILE
            ).revise(
                review,
                tuple(revised_artifacts),
                expected_revision=review.revision,
                reviewer_id=reviewer,
            )
            st.session_state[AGILE_REVIEW_STATE_KEY] = revised_review
        except AgileReviewError as error:
            st.error(str(error))
            return
        st.rerun()

    accept_column, reject_column = st.columns(2)
    accept = accept_column.button(
        "Accept Agile batch",
        type="primary",
        disabled=not review.can_accept,
        key=f"agile_accept_{review.review_id}_{review.revision}",
        width="stretch",
    )
    with reject_column.form(f"agile_reject_form_{review.review_id}_{review.revision}"):
        rejection_reason = st.text_input(
            "Rejection reason *",
            key=f"agile_rejection_reason_{review.review_id}_{review.revision}",
        )
        reject = st.form_submit_button("Reject Agile batch", width="stretch")
    if reject:
        try:
            st.session_state[AGILE_REVIEW_STATE_KEY] = AgileReviewService(
                _agile_review_retriever(), APP_DATABASE_FILE
            ).reject(
                review,
                expected_revision=review.revision,
                reviewer_id=reviewer,
                reason=rejection_reason,
            )
        except AgileReviewError as error:
            st.error(str(error))
            return
        st.rerun()
    if not accept:
        return
    try:
        result = AgileReviewService(
            _agile_review_retriever(), APP_DATABASE_FILE
        ).accept(
            review,
            expected_revision=review.revision,
            reviewer_id=reviewer,
        )
        st.session_state[AGILE_REVIEW_STATE_KEY] = result.review
    except AgileReviewError as error:
        st.error(str(error))
        return
    st.rerun()


def render_agile_assistant() -> None:
    """Expose Checkpoints 7–10 through source-scoped, governed controls."""

    st.subheader("Governed Agile artifacts")
    st.caption(
        "Generate Epics, Capabilities, Features, User Stories, or structured "
        "acceptance criteria from intentionally selected Approved sources."
    )
    try:
        products = list_products(APP_DATABASE_FILE)
    except (DatabaseSchemaError, sqlite3.Error):
        display_database_error()
        return
    if not products:
        st.info("No products are available. Create a product before Agile generation.")
        return
    products_by_id = {product.id: product for product in products if product.id}
    product_id = st.selectbox(
        "Product",
        [None, *products_by_id],
        format_func=lambda value: "Select a product" if value is None else product_option_label(products_by_id[value]),
        key="agile_product_id",
    )
    documents = (
        list_documents_for_product(product_id, APP_DATABASE_FILE)
        if isinstance(product_id, int)
        else []
    )
    approved = {
        document.id: document
        for document in documents
        if document.id and document.document_status is DocumentStatus.APPROVED
    }
    selected_documents = st.multiselect(
        "Approved BRD/PRD grounding sources",
        options=list(approved),
        format_func=lambda value: document_option_label(approved[value]),
        key="agile_document_ids",
    )
    if product_id is not None and not approved:
        st.info("This product has no Approved BRD or PRD sources. Drafts are ineligible.")

    selected_label = st.selectbox(
        "Agile artifact type",
        options=[item[0] for item in AGILE_TYPE_OPTIONS],
        key="agile_artifact_type",
    )
    _, task, artifact_type = next(
        item for item in AGILE_TYPE_OPTIONS if item[0] == selected_label
    )
    if task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA:
        artifact_type = st.selectbox(
            "Artifact type for the criteria",
            options=list(AgileArtifactType),
            format_func=lambda value: value.value.replace("_", " ").title(),
            key="agile_criteria_artifact_type",
        )
    prompt = get_agile_prompt(
        "agile-acceptance-criteria" if task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA else f"agile-{artifact_type.value}",
        "1.0.0",
        task,
        artifact_type,
    )
    st.info(f"Approved prompt: {prompt.name} · {prompt.prompt_id} · version {prompt.version}")

    profile_by_value = {
        definition.profile.value: definition for definition in AGILE_PROFILE_DEFINITIONS
    }
    profile_value = st.selectbox(
        "Approved behavior profile",
        options=list(profile_by_value),
        index=list(profile_by_value).index(DEFAULT_AGILE_PROFILE.value),
        format_func=lambda value: profile_by_value[value].display_name,
        key="agile_profile",
    )
    st.caption(profile_by_value[profile_value].description)
    top_k = st.number_input(
        "Retrieval Top-K",
        min_value=1,
        max_value=50,
        value=5,
        help="This retrieval limit is separate from internal generation controls.",
        key="agile_top_k",
    )
    st.caption(
        "Generation sampling, optimization, and hallucination-control settings are "
        "internal and are not configurable here or in the PRD."
    )

    accepted_artifacts = []
    if isinstance(product_id, int):
        for batch in list_accepted_agile_batches_for_product(product_id, APP_DATABASE_FILE):
            accepted_artifacts.extend(batch.artifacts)
    required_parent_type = (
        artifact_type
        if task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA
        else PARENT_TYPE[artifact_type]
    )
    candidates = {
        artifact.artifact_id: artifact
        for artifact in accepted_artifacts
        if artifact.artifact_type is required_parent_type
    }
    parent_id = None
    if required_parent_type is not None:
        parent_id = st.selectbox(
            (
                "Artifact receiving the criteria *"
                if task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA
                else f"Applicable {required_parent_type.value.replace('_', ' ').title()} parent"
            ),
            options=[None, *candidates],
            format_func=lambda value: "Select an artifact" if value is None else f"{candidates[value].title} · {value}",
            key="agile_parent_id",
        )
        if task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA and not candidates:
            st.info("Accept a matching Agile artifact before generating its criteria.")

    with st.form("agile_generation_form"):
        request_text = st.text_area(
            "Product Manager request *",
            max_chars=10_000,
            placeholder="Describe the grounded Agile outcome to generate.",
            key="agile_request_text",
        )
        reviewer_id = st.text_input(
            "Reviewer identity *",
            value="Product Manager",
            key="agile_generation_reviewer",
        )
        generate = st.form_submit_button("Generate Agile draft", type="primary")

    if generate:
        if product_id is None:
            st.error("Select a product before generation.")
        elif not selected_documents:
            st.error("Select one or more Approved BRD/PRD grounding sources.")
        elif task is AgilePromptTask.GENERATE_ACCEPTANCE_CRITERIA and parent_id is None:
            st.error("Select the artifact that will receive the acceptance criteria.")
        else:
            parent = None
            if parent_id is not None:
                selected_parent = candidates[parent_id]
                parent = AgileParentContext(
                    selected_parent.artifact_id,
                    selected_parent.artifact_type,
                    selected_parent.product_id,
                    selected_parent.title,
                )
            generation_request = AgileGenerationRequest(
                product_id=product_id,
                selected_document_ids=tuple(selected_documents),
                artifact_type=artifact_type,
                task=task,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
                request_text=request_text,
                profile=profile_value,
                retrieval_controls=RetrievalControls(int(top_k)),
                parent=parent,
            )
            signature = (
                product_id,
                tuple(selected_documents),
                task.value,
                artifact_type.value,
                parent_id,
                profile_value,
                int(top_k),
                request_text.strip(),
            )
            previous = st.session_state.get(AGILE_SUBMISSION_STATE_KEY)
            if previous == signature and isinstance(
                st.session_state.get(AGILE_REVIEW_STATE_KEY), AgileReviewBatch
            ):
                st.info("This Agile submission was already processed; no duplicate call was made.")
            else:
                try:
                    retriever, ai_service = _agile_runtime()
                    generation = GroundedAgileGenerationService(
                        retriever,
                        ai_service,
                        capabilities=ModelCapabilities(
                            "openai", ai_service.model, True, False, False
                        ),
                    ).generate(generation_request)
                    if generation.state not in {
                        AgileGenerationState.GENERATED,
                        AgileGenerationState.SUPPORT_BLOCKED,
                    }:
                        st.warning(generation.message)
                    else:
                        st.session_state[AGILE_REVIEW_STATE_KEY] = AgileReviewService(
                            retriever, APP_DATABASE_FILE
                        ).begin_review(
                            generation_request,
                            generation,
                            reviewer_id=reviewer_id,
                        )
                        st.session_state[AGILE_SUBMISSION_STATE_KEY] = signature
                except (AIConfigurationError, AIServiceError, AgileGenerationError, AgileReviewError) as error:
                    st.error(str(error))
                except (DatabaseSchemaError, sqlite3.Error, ValueError):
                    st.error("Agile generation failed safely; no content was saved.")

    review = st.session_state.get(AGILE_REVIEW_STATE_KEY)
    if isinstance(review, AgileReviewBatch):
        render_agile_review(review)
    else:
        st.info("Nothing is saved automatically. Generate, inspect every gate, then accept, revise, or reject.")


def render_ai_assistant() -> None:
    """Render governed Agile and original grounded-draft workflows."""

    st.header("AI Assistant")
    st.write(
        "PMC uses optional grounded AI to help Product Managers draft and review "
        "Agile artifacts from intentionally selected Approved BRDs and PRDs. "
        "AI does not write or approve product decisions independently."
    )
    st.caption(
        "Citations, source-freshness checks, claim-support assessment, human "
        "review, and explicit acceptance are required responsible-AI controls."
    )
    configuration = get_ai_configuration()
    if configuration.configured:
        st.success(
            "AI Assistant status: Active. A session API key is configured for this "
            "PMC process. The provider validates the key when an AI feature is used."
        )
    else:
        st.info(
            "AI Assistant status: Inactive. AI-assisted Agile generation and General "
            "draft generation are unavailable. Manual Product, BRD, PRD, search, "
            "review-history, and export functions remain available without AI."
        )
    with st.expander("Activate AI Assistant", expanded=not configuration.configured):
        st.markdown(
            "AI-assisted generation requires a valid API key supplied by you. The "
            "key authorizes use of the configured AI provider; it does **not** give "
            "PMC or the provider automatic access to company information. Enterprise "
            "users should request an organization-approved key and data-use "
            "authorization from their IT, security, AI-governance, or platform-"
            "administration team."
        )
        st.warning(
            "Do not send confidential, proprietary, regulated, personal, export-"
            "controlled, or customer information to an external provider without "
            "organizational approval. Only deliberately selected Approved BRD/PRD "
            "content is submitted by PMC when you request generation."
        )
        st.markdown(
            "To activate AI temporarily on macOS, stop PMC and use the same Terminal "
            "session to run `read -s OPENAI_API_KEY`, `export OPENAI_API_KEY`, and "
            "`scripts/start_pmc_macos.command`. After pressing Control-C to stop PMC, "
            "run `unset OPENAI_API_KEY`. Never paste a key into PMC or store or expose "
            "it in source code, Git, SQLite, logs, documents, exports, screenshots, "
            "or release packages. Normal startup never asks for a key."
        )
    agile_tab, general_tab = st.tabs(("Agile generation and review", "General draft"))
    with agile_tab:
        render_agile_assistant()
    with general_tab:
        render_general_assistant()


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
        contributors = [
            {"entry_id": row.entry_id, "position": row.position,
             "contributor_name": row.contributor_name, "contributor_role": row.contributor_role}
            for row in document.contributors
        ]
        if not contributors and document_type is DocumentType.PRD and document.sections.get("contributors_roles"):
            contributors = [{"entry_id": "", "position": 1,
                             "contributor_name": document.sections["contributors_roles"],
                             "contributor_role": ""}]
        milestones = [
            {"entry_id": row.entry_id, "position": row.position,
             "date": row.date, "milestone": row.milestone}
            for row in document.key_dates_milestones
        ]
        if not milestones and document_type is DocumentType.PRD:
            legacy_date = document.sections.get("key_dates", "")
            legacy_milestone = document.sections.get("milestones", "")
            if legacy_date or legacy_milestone:
                milestones = [{"entry_id": "", "position": 1,
                               "date": legacy_date, "milestone": legacy_milestone}]
        brd_hierarchy = []
        for row in document.brd_hierarchy:
            item = {"row_id": row.row_id, "position": row.position}
            for level in ("epic", "capability", "feature", "user_story"):
                item[f"{level}_id"] = getattr(row, f"{level}_id")
                item[level] = getattr(row, level)
                if level != "epic":
                    item[f"{level}_parent_id"] = getattr(row, f"{level}_parent_id")
                item[f"{level}_acceptance_criteria"] = [
                    {"criterion_id": criterion.criterion_id,
                     "position": criterion.position, "text": criterion.text}
                    for criterion in getattr(row, f"{level}_acceptance_criteria")
                ]
            brd_hierarchy.append(item)
        if not brd_hierarchy and document_type is DocumentType.BRD:
            legacy_keys = {"epic": "epics", "capability": "capabilities",
                           "feature": "features", "user_story": "user_stories"}
            if any(document.sections.get(key) for key in (*legacy_keys.values(), "acceptance_criteria")):
                brd_hierarchy = [{
                    "row_id": "", "position": 1,
                    **{level: document.sections.get(key, "") for level, key in legacy_keys.items()},
                    **{f"{level}_id": "" for level in legacy_keys},
                    "capability_parent_id": "", "feature_parent_id": "", "user_story_parent_id": "",
                    "epic_acceptance_criteria": [], "capability_acceptance_criteria": [],
                    "feature_acceptance_criteria": [],
                    "user_story_acceptance_criteria": ([{"criterion_id": "", "position": 1,
                        "text": document.sections.get("acceptance_criteria", "")}]
                        if document.sections.get("acceptance_criteria") else []),
                }]
        brd_risks = [
            {"entry_id": row.entry_id, "position": row.position,
             "business_risk": row.business_risk, "mitigation_strategy": row.mitigation_strategy}
            for row in document.brd_risks
        ]
        if not brd_risks and document_type is DocumentType.BRD:
            risk = document.sections.get("business_risks", "")
            mitigation = document.sections.get("mitigation_strategies", "")
            if risk or mitigation:
                brd_risks = [{"entry_id": "", "position": 1,
                              "business_risk": risk, "mitigation_strategy": mitigation}]
        return {
            "title": document.title,
            "version": document.version,
            "document_status": document.document_status,
            "sections": dict(document.sections),
            "success_matrix": [
                {
                    "entry_id": entry.entry_id,
                    "position": entry.position,
                    "requirement_outcome": entry.requirement_outcome,
                    "metric": entry.metric,
                    "baseline": entry.baseline or "",
                    "target": entry.target,
                    "minimum_acceptance_threshold": entry.minimum_acceptance_threshold,
                    "measurement_method": entry.measurement_method,
                    "data_source": entry.data_source,
                    "evaluation_period": entry.evaluation_period,
                    "validation_owner": entry.validation_owner,
                    "status": entry.status.value if entry.status else "",
                }
                for entry in document.success_matrix
            ],
            "agile_hierarchy": [
                {
                    "artifact_id": artifact.artifact_id,
                    "artifact_type": artifact.artifact_type,
                    "position": artifact.position,
                    "title": artifact.title,
                    "description": artifact.description,
                    "parent_artifact_id": artifact.parent_artifact_id,
                    "acceptance_criteria": [
                        {
                            "criterion_id": criterion.criterion_id,
                            "position": criterion.position,
                            "text": criterion.text,
                        }
                        for criterion in artifact.acceptance_criteria
                    ],
                }
                for artifact in document.agile_hierarchy
            ],
            "contributors": contributors,
            "key_dates_milestones": milestones,
            "brd_hierarchy": brd_hierarchy,
            "brd_risks": brd_risks,
        }
    return {
        "title": derived_document_title(product, document_type),
        "version": "1.0",
        "document_status": DocumentStatus.DRAFT,
        "sections": prepopulated_sections(product, document_type),
        "success_matrix": [],
        "agile_hierarchy": [],
        "contributors": [],
        "key_dates_milestones": [],
        "brd_hierarchy": [],
        "brd_risks": [],
    }


def repeatable_count_controls(
    key_prefix: str, field: str, label: str, starting_count: int
) -> int:
    """Expose explicit Add/Remove actions while retaining stable indexed state."""

    count_key = f"{key_prefix}_{field}_count"
    if count_key not in st.session_state:
        st.session_state[count_key] = starting_count
    add_column, remove_column, summary_column = st.columns((1, 1, 2))
    if add_column.button(f"Add {label}", key=f"{count_key}_add"):
        st.session_state[count_key] = int(st.session_state[count_key]) + 1
    if remove_column.button(
        f"Remove {label}", key=f"{count_key}_remove",
        disabled=int(st.session_state[count_key]) == 0,
    ):
        st.session_state[count_key] = max(0, int(st.session_state[count_key]) - 1)
    count = int(st.number_input(
        f"Number of {label} entries", min_value=0, step=1,
        key=count_key,
        help="This is an informational editing control; no predetermined item count is required.",
    ))
    summary_column.caption(f"{label} count: {count}")
    return count


def prepare_prd_hierarchy_controls(
    key_prefix: str,
    document: ProductDocument | None,
) -> None:
    """Render repeatable hierarchy counts outside the document save form."""

    existing = tuple(document.agile_hierarchy) if document is not None else ()
    st.markdown("##### Structured Agile hierarchy")
    st.caption(
        "Epic → Capability → Feature → User Story. Functional requirements remain "
        "a separate PRD section and are not a hierarchy level."
    )
    for artifact_type in AgileArtifactType:
        entries = tuple(
            item for item in existing if item.artifact_type is artifact_type
        )
        label = artifact_type.value.replace("_", " ").title()
        count = repeatable_count_controls(
            key_prefix, f"agile_{artifact_type.value}", label, len(entries)
        )
        for index in range(count):
            artifact_key = f"{key_prefix}_agile_{artifact_type.value}_{index}"
            artifact_id_key = f"{artifact_key}_id"
            if artifact_id_key not in st.session_state:
                st.session_state[artifact_id_key] = (
                    entries[index].artifact_id
                    if index < len(entries)
                    else f"prd-agile-{uuid4().hex}"
                )
            criterion_count = (
                len(entries[index].acceptance_criteria)
                if index < len(entries)
                else 0
            )
            repeatable_count_controls(
                artifact_key, "criterion",
                f"criterion for {label} {index + 1}", criterion_count,
            )


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

    st.markdown("#### Guided professional outline")
    sections: dict[str, str] = {}
    current_group: str | None = None
    hidden_structured_keys = {
        DocumentType.PRD: {"contributors_roles", "key_dates", "milestones"},
        DocumentType.BRD: {
            "epics", "capabilities", "features", "user_stories",
            "acceptance_criteria", "business_risks", "mitigation_strategies",
        },
    }
    special_help = {
        "tracking_strategy": (
            "Explain how, where, and how frequently product performance will be monitored. "
            "Example: Track scheduling starts, completions, abandonment, errors, and "
            "appointment outcomes through product analytics dashboards. Review weekly "
            "during beta and monthly after launch."
        ),
        "analytics_telemetry": (
            "List the specific product events, signals, or logs required for measurement. "
            "Examples: scheduling_started, availability_viewed, appointment_selected, "
            "appointment_confirmed, appointment_rescheduled, appointment_cancelled, "
            "scheduling_failed. Examples are guidance only and are not saved automatically."
        ),
    }
    for definition in document_template(document_type):
        if definition.group != current_group:
            st.markdown(f"##### {definition.group}")
            current_group = definition.group
        if definition.key in hidden_structured_keys[document_type]:
            sections[definition.key] = st.text_area(
                f"Legacy {definition.label} (preserved)",
                value=values["sections"].get(definition.key, ""),
                max_chars=DOCUMENT_SECTION_MAX_LENGTH,
                help=(
                    "Backward-compatible source text. It is retained without overwrite; "
                    "use the structured editor for new content."
                ),
                disabled=True,
                label_visibility="collapsed",
                key=f"{key_prefix}_section_{definition.key}",
            )
            continue
        sections[definition.key] = st.text_area(
            definition.label,
            value=values["sections"].get(definition.key, ""),
            max_chars=DOCUMENT_SECTION_MAX_LENGTH,
            help=special_help.get(definition.key, definition.guidance),
            key=f"{key_prefix}_section_{definition.key}",
        )

    contributors: list[dict[str, object]] = []
    key_dates_milestones: list[dict[str, object]] = []
    brd_hierarchy: list[dict[str, object]] = []
    brd_risks: list[dict[str, object]] = []
    success_matrix: list[dict[str, object]] = []
    if document_type is DocumentType.PRD:
        st.markdown("##### Contributors and Roles")
        contributor_count = int(st.session_state.get(
            f"{key_prefix}_contributors_count", len(values["contributors"])
        ))
        for index in range(contributor_count):
            existing = values["contributors"][index] if index < len(values["contributors"]) else {}
            with st.expander(f"Contributor {index + 1}", expanded=True):
                contributors.append({
                    "entry_id": existing.get("entry_id", ""), "position": index + 1,
                    "contributor_name": st.text_input(
                        "Contributor name *", value=str(existing.get("contributor_name", "")),
                        key=f"{key_prefix}_contributor_{index}_name"),
                    "contributor_role": st.text_input(
                        "Contributor role *", value=str(existing.get("contributor_role", "")),
                        key=f"{key_prefix}_contributor_{index}_role"),
                })

        st.markdown("##### Key Dates and Milestones")
        milestone_count = int(st.session_state.get(
            f"{key_prefix}_key_dates_milestones_count", len(values["key_dates_milestones"])
        ))
        for index in range(milestone_count):
            existing = values["key_dates_milestones"][index] if index < len(values["key_dates_milestones"]) else {}
            with st.expander(f"Key Date and Milestone {index + 1}", expanded=True):
                key_dates_milestones.append({
                    "entry_id": existing.get("entry_id", ""), "position": index + 1,
                    "date": st.text_input("Date *", value=str(existing.get("date", "")),
                                          key=f"{key_prefix}_milestone_{index}_date"),
                    "milestone": st.text_input("Milestone *", value=str(existing.get("milestone", "")),
                                               key=f"{key_prefix}_milestone_{index}_milestone"),
                })

        st.markdown("##### Structured Agile hierarchy")
        st.write(
            "Author repeatable items using the explicit Epic → Capability → Feature "
            "→ User Story hierarchy. Each item owns its acceptance criteria; criteria "
            "are never copied to or used as proof for another level."
        )
        existing_by_type = {
            artifact_type: [
                item
                for item in values["agile_hierarchy"]
                if item["artifact_type"] is artifact_type
            ]
            for artifact_type in AgileArtifactType
        }
        artifact_specs: dict[AgileArtifactType, list[tuple[str, dict[str, object]]]] = {}
        for artifact_type in AgileArtifactType:
            count = int(
                st.session_state.get(
                    f"{key_prefix}_agile_{artifact_type.value}_count",
                    len(existing_by_type[artifact_type]),
                )
            )
            artifact_specs[artifact_type] = []
            for index in range(count):
                artifact_key = f"{key_prefix}_agile_{artifact_type.value}_{index}"
                existing = (
                    existing_by_type[artifact_type][index]
                    if index < len(existing_by_type[artifact_type])
                    else {}
                )
                artifact_id = str(
                    st.session_state.get(
                        f"{artifact_key}_id",
                        existing.get("artifact_id") or f"prd-agile-{uuid4().hex}",
                    )
                )
                st.session_state[f"{artifact_key}_id"] = artifact_id
                artifact_specs[artifact_type].append((artifact_id, existing))

        agile_hierarchy: list[dict[str, object]] = []
        for artifact_type in AgileArtifactType:
            parent_type = PARENT_TYPE[artifact_type]
            parent_options = (
                []
                if parent_type is None
                else [item[0] for item in artifact_specs[parent_type]]
            )
            for index, (artifact_id, existing) in enumerate(
                artifact_specs[artifact_type]
            ):
                artifact_key = f"{key_prefix}_agile_{artifact_type.value}_{index}"
                with st.expander(
                    f"{artifact_type.value.replace('_', ' ').title()} {index + 1}",
                    expanded=True,
                ):
                    parent_id = None
                    if parent_type is not None:
                        existing_parent = existing.get("parent_artifact_id")
                        options = [None, *parent_options]
                        parent_id = st.selectbox(
                            f"Parent {parent_type.value.replace('_', ' ').title()} *",
                            options=options,
                            index=(
                                options.index(existing_parent)
                                if existing_parent in options
                                else 0
                            ),
                            format_func=lambda value: (
                                "Select parent" if value is None else value
                            ),
                            key=f"{artifact_key}_parent",
                        )
                    title = st.text_input(
                        f"{artifact_type.value.replace('_', ' ').title()} title *",
                        value=str(existing.get("title", "")),
                        max_chars=200,
                        key=f"{artifact_key}_title",
                    )
                    description = st.text_area(
                        f"{artifact_type.value.replace('_', ' ').title()} description *",
                        value=str(existing.get("description", "")),
                        max_chars=10_000,
                        key=f"{artifact_key}_description",
                    )
                    existing_criteria = list(existing.get("acceptance_criteria", ()))
                    criterion_count = int(
                        st.session_state.get(
                            f"{artifact_key}_criterion_count",
                            len(existing_criteria),
                        )
                    )
                    criteria: list[dict[str, object]] = []
                    st.markdown("**Acceptance criteria**")
                    for criterion_index in range(criterion_count):
                        criterion_key = (
                            f"{artifact_key}_criterion_{criterion_index}"
                        )
                        existing_criterion = (
                            existing_criteria[criterion_index]
                            if criterion_index < len(existing_criteria)
                            else {}
                        )
                        criterion_id_key = f"{criterion_key}_id"
                        if criterion_id_key not in st.session_state:
                            st.session_state[criterion_id_key] = (
                                existing_criterion.get("criterion_id")
                                or f"prd-criterion-{uuid4().hex}"
                            )
                        criteria.append(
                            {
                                "criterion_id": st.session_state[criterion_id_key],
                                "position": criterion_index + 1,
                                "text": st.text_area(
                                    f"Criterion {criterion_index + 1} *",
                                    value=str(existing_criterion.get("text", "")),
                                    max_chars=2_000,
                                    key=f"{criterion_key}_text",
                                ),
                            }
                        )
                    agile_hierarchy.append(
                        {
                            "artifact_id": artifact_id,
                            "artifact_type": artifact_type,
                            "position": index + 1,
                            "title": title,
                            "description": description,
                            "parent_artifact_id": parent_id,
                            "acceptance_criteria": criteria,
                        }
                    )
        hierarchy_counts = {
            artifact_type: len([row for row in agile_hierarchy if row["artifact_type"] is artifact_type])
            for artifact_type in AgileArtifactType
        }
        acceptance_count = sum(
            len(row["acceptance_criteria"]) for row in agile_hierarchy
        )
        st.caption(
            "Informational hierarchy summary — "
            f"Epics: {hierarchy_counts[AgileArtifactType.EPIC]} · "
            f"Capabilities: {hierarchy_counts[AgileArtifactType.CAPABILITY]} · "
            f"Features: {hierarchy_counts[AgileArtifactType.FEATURE]} · "
            f"User Stories: {hierarchy_counts[AgileArtifactType.USER_STORY]} · "
            f"Acceptance criteria: {acceptance_count}"
        )
        st.markdown("##### PRD Success Matrix")
        st.write(
            "Define measurable product outcomes here. These entries are separate "
            "from individual user-story acceptance criteria. Draft rows may be "
            "incomplete; approval requires the measurable fields in every row."
        )
        st.caption(
            "Express grounding quality as a measurable product outcome. Temperature, "
            "retrieval Top-K, generation Top-P, GEPA settings, and hallucination flags "
            "are internal controls and are not PRD fields."
        )
        entry_count = int(
            st.session_state.get(
                f"{key_prefix}_success_matrix_count",
                len(values["success_matrix"]),
            )
        )
        st.caption(f"Success Matrix entries: {entry_count}")
        field_labels = (
            ("requirement_outcome", "Requirement or desired outcome *"),
            ("metric", "Metric *"),
            ("baseline", "Baseline (when known)"),
            ("target", "Target *"),
            ("minimum_acceptance_threshold", "Minimum acceptance threshold *"),
            ("measurement_method", "Measurement method *"),
            ("data_source", "Data source *"),
            ("evaluation_period", "Evaluation period *"),
            ("validation_owner", "Validation owner *"),
        )
        for index in range(entry_count):
            existing = (
                values["success_matrix"][index]
                if index < len(values["success_matrix"])
                else {}
            )
            with st.expander(f"Success Matrix entry {index + 1}", expanded=True):
                row: dict[str, object] = {
                    "entry_id": existing.get("entry_id", ""),
                    "position": index + 1,
                }
                for field, label in field_labels:
                    row[field] = st.text_input(
                        label,
                        value=str(existing.get(field, "") or ""),
                        max_chars=2_000,
                        key=f"{key_prefix}_success_{index}_{field}",
                    )
                status_options: list[SuccessMatrixStatus | None] = [
                    None,
                    *SuccessMatrixStatus,
                ]
                existing_status = existing.get("status", "")
                selected_status = (
                    SuccessMatrixStatus(existing_status)
                    if existing_status
                    else None
                )
                row["status"] = st.selectbox(
                    "Status *",
                    options=status_options,
                    index=status_options.index(selected_status),
                    format_func=lambda value: (
                        "Select status"
                        if value is None
                        else value.value.replace("_", " ").title()
                    ),
                    key=f"{key_prefix}_success_{index}_status",
                )
                success_matrix.append(row)
    else:
        agile_hierarchy = []
        st.markdown("##### BRD Agile hierarchy")
        st.caption(
            "Use a readable row editor for Epic → Capability → Feature → User Story. "
            "Enter multiple acceptance criteria on separate lines; each level owns its criteria."
        )
        hierarchy_count = int(st.session_state.get(
            f"{key_prefix}_brd_hierarchy_count", len(values["brd_hierarchy"])
        ))
        levels = ("epic", "capability", "feature", "user_story")
        for index in range(hierarchy_count):
            existing = values["brd_hierarchy"][index] if index < len(values["brd_hierarchy"]) else {}
            row_id_key = f"{key_prefix}_brd_hierarchy_{index}_row_id"
            if row_id_key not in st.session_state:
                st.session_state[row_id_key] = existing.get("row_id") or f"brd-hierarchy-{uuid4().hex}"
            row_id = str(st.session_state[row_id_key])
            row: dict[str, object] = {"row_id": row_id, "position": index + 1}
            previous_id = ""
            with st.expander(f"BRD hierarchy row {index + 1}", expanded=True):
                for level in levels:
                    label = level.replace("_", " ").title()
                    item_id_key = f"{key_prefix}_brd_hierarchy_{index}_{level}_id"
                    if item_id_key not in st.session_state:
                        st.session_state[item_id_key] = existing.get(f"{level}_id") or f"brd-{level}-{uuid4().hex}"
                    item_id = str(st.session_state[item_id_key])
                    row[f"{level}_id"] = item_id
                    if level != "epic":
                        row[f"{level}_parent_id"] = previous_id
                    row[level] = st.text_area(
                        label, value=str(existing.get(level, "")),
                        key=f"{key_prefix}_brd_hierarchy_{index}_{level}")
                    existing_criteria = list(existing.get(f"{level}_acceptance_criteria", ()))
                    criteria_text = st.text_area(
                        f"{label} Acceptance Criteria",
                        value="\n".join(str(item.get("text", "")) for item in existing_criteria),
                        help="One measurable acceptance criterion per line.",
                        key=f"{key_prefix}_brd_hierarchy_{index}_{level}_criteria")
                    criteria_lines = [line.strip() for line in criteria_text.splitlines() if line.strip()]
                    criteria = []
                    for criterion_index, text in enumerate(criteria_lines):
                        criterion_id_key = f"{key_prefix}_brd_hierarchy_{index}_{level}_criterion_{criterion_index}_id"
                        if criterion_id_key not in st.session_state:
                            st.session_state[criterion_id_key] = (
                                existing_criteria[criterion_index].get("criterion_id")
                                if criterion_index < len(existing_criteria)
                                else f"brd-criterion-{uuid4().hex}"
                            )
                        criteria.append({"criterion_id": st.session_state[criterion_id_key],
                                         "position": criterion_index + 1, "text": text})
                    row[f"{level}_acceptance_criteria"] = criteria
                    previous_id = item_id
            brd_hierarchy.append(row)

        st.markdown("##### Business Risk and Mitigation Strategy")
        risk_count = int(st.session_state.get(
            f"{key_prefix}_brd_risks_count", len(values["brd_risks"])
        ))
        for index in range(risk_count):
            existing = values["brd_risks"][index] if index < len(values["brd_risks"]) else {}
            with st.expander(f"Business Risk and Mitigation Strategy {index + 1}", expanded=True):
                brd_risks.append({
                    "entry_id": existing.get("entry_id", ""), "position": index + 1,
                    "business_risk": st.text_area(
                        "Business Risk *", value=str(existing.get("business_risk", "")),
                        key=f"{key_prefix}_brd_risk_{index}_risk"),
                    "mitigation_strategy": st.text_area(
                        "Mitigation Strategy *", value=str(existing.get("mitigation_strategy", "")),
                        key=f"{key_prefix}_brd_risk_{index}_mitigation"),
                })
    if document_type is DocumentType.PRD:
        if not contributors and sections.get("contributors_roles"):
            contributors = [{
                "entry_id": "legacy-contributor-1", "position": 1,
                "contributor_name": sections["contributors_roles"], "contributor_role": "",
            }]
        if not key_dates_milestones and (sections.get("key_dates") or sections.get("milestones")):
            key_dates_milestones = [{
                "entry_id": "legacy-milestone-1", "position": 1,
                "date": sections.get("key_dates", ""),
                "milestone": sections.get("milestones", ""),
            }]
    else:
        if not brd_hierarchy and any(sections.get(key) for key in (
            "epics", "capabilities", "features", "user_stories", "acceptance_criteria"
        )):
            ids = {level: f"legacy-brd-{level}-1" for level in (
                "epic", "capability", "feature", "user_story"
            )}
            brd_hierarchy = [{
                "row_id": "legacy-brd-hierarchy-1", "position": 1,
                "epic_id": ids["epic"], "epic": sections.get("epics", ""),
                "epic_acceptance_criteria": [],
                "capability_id": ids["capability"], "capability_parent_id": ids["epic"],
                "capability": sections.get("capabilities", ""), "capability_acceptance_criteria": [],
                "feature_id": ids["feature"], "feature_parent_id": ids["capability"],
                "feature": sections.get("features", ""), "feature_acceptance_criteria": [],
                "user_story_id": ids["user_story"], "user_story_parent_id": ids["feature"],
                "user_story": sections.get("user_stories", ""),
                "user_story_acceptance_criteria": ([{
                    "criterion_id": "legacy-brd-user-story-criterion-1", "position": 1,
                    "text": sections.get("acceptance_criteria", ""),
                }] if sections.get("acceptance_criteria") else []),
            }]
        if not brd_risks and (sections.get("business_risks") or sections.get("mitigation_strategies")):
            brd_risks = [{
                "entry_id": "legacy-brd-risk-1", "position": 1,
                "business_risk": sections.get("business_risks", ""),
                "mitigation_strategy": sections.get("mitigation_strategies", ""),
            }]
    return {
        "title": title,
        "version": version,
        "document_status": document_status,
        "sections": sections,
        "success_matrix": success_matrix,
        "agile_hierarchy": agile_hierarchy,
        "contributors": contributors,
        "key_dates_milestones": key_dates_milestones,
        "brd_hierarchy": brd_hierarchy,
        "brd_risks": brd_risks,
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


def clear_stale_page_state(selected_section: str) -> None:
    """Prevent transient form or review evidence leaking across page changes."""

    previous = st.session_state.get(LAST_NAVIGATION_KEY)
    if previous is None:
        st.session_state[LAST_NAVIGATION_KEY] = selected_section
        return
    if previous == selected_section:
        return
    preserved = {NAVIGATION_STATE_KEY, LAST_NAVIGATION_KEY}
    transient_prefixes = (
        "primary_create_",
        "generated_content_",
        "grounded_generation_",
        "agile_",
    )
    for key in tuple(st.session_state):
        if key not in preserved and (
            key in {
                GENERATED_REVIEW_STATE_KEY,
                GENERATION_SUBMISSION_STATE_KEY,
                AGILE_REVIEW_STATE_KEY,
                AGILE_SUBMISSION_STATE_KEY,
            }
            or key.startswith(transient_prefixes)
        ):
            st.session_state.pop(key, None)
    st.session_state[LAST_NAVIGATION_KEY] = selected_section


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
    current_group: str | None = None
    hidden_structured_keys = {
        DocumentType.PRD: {"contributors_roles", "key_dates", "milestones"},
        DocumentType.BRD: {
            "epics", "capabilities", "features", "user_stories",
            "acceptance_criteria", "business_risks", "mitigation_strategies",
        },
    }
    for definition in document_template(document.document_type):
        if definition.group != current_group:
            st.markdown(f"## {definition.group}")
            current_group = definition.group
        if definition.key in hidden_structured_keys[document.document_type]:
            continue
        st.markdown(f"### {definition.label}")
        st.write(document.sections.get(definition.key) or "Not provided")
    if document.document_type is DocumentType.PRD:
        st.markdown("## Contributors and Roles")
        if document.contributors:
            st.dataframe(
                [{"Contributor name": row.contributor_name,
                  "Contributor role": row.contributor_role}
                 for row in document.contributors],
                hide_index=True, width="stretch",
            )
        else:
            st.write("No Contributors and Roles entries provided.")
        st.markdown("## Key Dates and Milestones")
        if document.key_dates_milestones:
            st.dataframe(
                [{"Date": row.date, "Milestone": row.milestone}
                 for row in document.key_dates_milestones],
                hide_index=True, width="stretch",
            )
        else:
            st.write("No Key Dates and Milestones entries provided.")
        st.markdown("## Structured Agile hierarchy")
        if document.agile_hierarchy:
            for artifact in document.agile_hierarchy:
                st.markdown(
                    f"### {artifact.artifact_type.value.replace('_', ' ').title()} "
                    f"{artifact.position}: {artifact.title or 'Untitled'}"
                )
                st.caption(
                    f"ID: {artifact.artifact_id} · "
                    f"Parent: {artifact.parent_artifact_id or 'None'}"
                )
                st.write(artifact.description or "Not provided")
                st.markdown("**Acceptance criteria**")
                if artifact.acceptance_criteria:
                    for criterion in artifact.acceptance_criteria:
                        st.write(
                            f"{criterion.position}. {criterion.text or 'Not provided'} "
                            f"({criterion.criterion_id})"
                        )
                else:
                    st.write("No acceptance criteria provided.")
        else:
            st.write(
                "No structured hierarchy entries provided. Legacy PRD section text "
                "remains available above."
            )
        hierarchy_counts = {
            artifact_type: len([
                row for row in document.agile_hierarchy
                if row.artifact_type is artifact_type
            ])
            for artifact_type in AgileArtifactType
        }
        acceptance_count = sum(len(row.acceptance_criteria) for row in document.agile_hierarchy)
        st.caption(
            "Informational hierarchy summary — "
            f"Epics: {hierarchy_counts[AgileArtifactType.EPIC]} · "
            f"Capabilities: {hierarchy_counts[AgileArtifactType.CAPABILITY]} · "
            f"Features: {hierarchy_counts[AgileArtifactType.FEATURE]} · "
            f"User Stories: {hierarchy_counts[AgileArtifactType.USER_STORY]} · "
            f"Acceptance criteria: {acceptance_count}"
        )
        st.markdown("## PRD Success Matrix")
        st.caption(
            "Measurable PRD outcomes; distinct from user-story acceptance criteria."
        )
        st.caption(f"Success Matrix entries: {len(document.success_matrix)}")
        if document.success_matrix:
            st.dataframe(
                [
                    {
                        "ID": entry.entry_id,
                        "Order": entry.position,
                        "Requirement or desired outcome": entry.requirement_outcome,
                        "Metric": entry.metric,
                        "Baseline": entry.baseline or "Not known",
                        "Target": entry.target,
                        "Minimum acceptance threshold": entry.minimum_acceptance_threshold,
                        "Measurement method": entry.measurement_method,
                        "Data source": entry.data_source,
                        "Evaluation period": entry.evaluation_period,
                        "Validation owner": entry.validation_owner,
                        "Status": entry.status.value if entry.status else "Not provided",
                    }
                    for entry in document.success_matrix
                ],
                hide_index=True,
                width="stretch",
            )
        else:
            st.write("No Success Matrix entries provided.")
    else:
        st.markdown("## BRD Agile hierarchy")
        if document.brd_hierarchy:
            def criteria_text(criteria: object) -> str:
                return "\n".join(
                    f"{item.position}. {item.text}" for item in criteria
                )
            st.dataframe(
                [{
                    "Epic": row.epic,
                    "Epic Acceptance Criteria": criteria_text(row.epic_acceptance_criteria),
                    "Capability": row.capability,
                    "Capability Acceptance Criteria": criteria_text(row.capability_acceptance_criteria),
                    "Feature": row.feature,
                    "Feature Acceptance Criteria": criteria_text(row.feature_acceptance_criteria),
                    "User Story": row.user_story,
                    "User Story Acceptance Criteria": criteria_text(row.user_story_acceptance_criteria),
                } for row in document.brd_hierarchy],
                hide_index=True, width="stretch",
            )
        else:
            st.write("No structured BRD hierarchy rows provided; legacy text remains preserved.")
        st.markdown("## Business Risk and Mitigation Strategy")
        if document.brd_risks:
            st.dataframe(
                [{"Business Risk": row.business_risk,
                  "Mitigation Strategy": row.mitigation_strategy}
                 for row in document.brd_risks],
                hide_index=True, width="stretch",
            )
        else:
            st.write("No structured Business Risk and Mitigation Strategy entries provided.")
    st.caption(
        f"Created: {document.created_at or 'Not available'}  ·  "
        f"Updated: {document.updated_at or 'Not available'}"
    )


def render_document_downloads(document: ProductDocument, product: Product) -> None:
    """Provide read-only, in-memory Word and PDF downloads for one saved document."""

    st.markdown("### Download saved document")
    st.caption(
        "Exports use the saved document content shown above. Downloading does not "
        "change the document or require an API key."
    )
    generated_at = datetime.now(timezone.utc)
    try:
        word = create_document_export(
            product,
            document,
            ExportFormat.DOCX,
            generated_at=generated_at,
        )
        pdf = create_document_export(
            product,
            document,
            ExportFormat.PDF,
            generated_at=generated_at,
        )
    except DocumentExportError:
        st.error("This saved document could not be exported safely. Please try again.")
        return

    word_column, pdf_column = st.columns(2)
    word_column.download_button(
        "Download Word (.docx)",
        data=word.content,
        file_name=word.filename,
        mime=word.mime_type,
        width="stretch",
        key=f"document_word_export_{document.id}",
    )
    pdf_column.download_button(
        "Download PDF (.pdf)",
        data=pdf.content,
        file_name=pdf.filename,
        mime=pdf.mime_type,
        width="stretch",
        key=f"document_pdf_export_{document.id}",
    )


def render_accepted_artifact_history(product: Product) -> None:
    """Display a product's separately stored accepted AI artifacts read-only."""

    if product.id is None:
        return
    st.divider()
    st.subheader("Accepted AI-generated artifacts")
    st.caption(
        "Read-only history. These accepted artifacts are stored separately from "
        "the original BRDs and PRDs and cannot change source documents."
    )
    try:
        artifacts = list_generated_artifacts_for_product(
            product.id,
            APP_DATABASE_FILE,
        )
    except (DatabaseSchemaError, sqlite3.Error):
        st.error(
            "Accepted-artifact history could not be loaded safely. Please try "
            "again."
        )
        return

    if not artifacts:
        st.info(
            "No accepted AI-generated artifacts for this product yet. Generated "
            "content appears here only after explicit human acceptance."
        )
        return

    for artifact in artifacts:
        with st.expander(
            f"Accepted artifact {artifact.id} · {artifact.accepted_at}",
        ):
            st.markdown(
                f"**Associated product:** {product.name} (ID {product.id})"
            )
            st.markdown("**Purpose / original request**")
            st.write(artifact.request)
            st.markdown("**Accepted content**")
            st.write(artifact.accepted_content)
            if artifact.was_revised:
                st.caption(
                    "A human revised this content before explicitly accepting it."
                )
                st.markdown("**Original AI output retained for comparison**")
                st.write(artifact.original_content)
            else:
                st.caption("Accepted without a human text revision.")
            st.markdown("**Supporting source citations**")
            for citation in artifact.citations:
                st.markdown(
                    f"**[Source {citation.source_number}]** "
                    f"{citation.source_product_name} "
                    f"(product ID {citation.source_product_id}) · "
                    f"{citation.document_title} (document ID {citation.document_id}) "
                    f"· {citation.document_type.value} · {citation.section_title}"
                )
            st.caption(
                f"Created: {artifact.created_at} · Accepted: {artifact.accepted_at}"
            )


def render_accepted_agile_history(product: Product) -> None:
    """Display accepted governed Agile batches separately from documents."""

    if product.id is None:
        return
    st.divider()
    st.subheader("Accepted Agile artifacts")
    st.caption(
        "Read-only accepted batches with immutable source traceability. Pending, "
        "blocked, revised, and rejected candidates never appear here."
    )
    try:
        batches = list_accepted_agile_batches_for_product(
            product.id, APP_DATABASE_FILE
        )
    except (DatabaseSchemaError, sqlite3.Error):
        st.error("Accepted Agile history could not be loaded safely.")
        return
    if not batches:
        st.info("No accepted Agile batches for this product yet.")
        return
    for batch in batches:
        with st.expander(
            f"Batch {batch.batch_id} · {batch.behavior_profile.value.replace('_', ' ').title()}"
        ):
            st.caption(
                f"Prompt version {batch.prompt_version} · revision {batch.revision} · "
                f"accepted {batch.accepted_at}"
            )
            for artifact in batch.artifacts:
                st.markdown(
                    f"**{artifact.position}. {artifact.artifact_type.value.replace('_', ' ').title()}: "
                    f"{artifact.title}**"
                )
                st.write(artifact.description)
                for criterion in artifact.acceptance_criteria:
                    st.write(f"- {criterion.text}")
                st.markdown("Sources")
                _display_agile_sources(artifact.source_references)


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
    starting_values = editable_document_values(product, document_type, document)
    if document_type is DocumentType.PRD:
        prepare_prd_hierarchy_controls(form_key, document)
        repeatable_count_controls(
            form_key, "contributors", "Contributor and Role",
            len(starting_values["contributors"]),
        )
        repeatable_count_controls(
            form_key, "key_dates_milestones", "Key Date and Milestone",
            len(starting_values["key_dates_milestones"]),
        )
        repeatable_count_controls(
            form_key, "success_matrix", "Success Matrix entry",
            len(starting_values["success_matrix"]),
        )
    else:
        repeatable_count_controls(
            form_key, "brd_hierarchy", "BRD hierarchy row",
            len(starting_values["brd_hierarchy"]),
        )
        repeatable_count_controls(
            form_key, "brd_risks", "Business Risk and Mitigation Strategy",
            len(starting_values["brd_risks"]),
        )
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
    render_document_downloads(document, product)
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


def render_getting_started() -> None:
    """Explain the safe local workflow and offer optional fictional data."""

    st.subheader("Getting Started")
    st.write(
        "Product Manager Central (PMC) is a local workspace for organizing "
        "products, writing BRDs and PRDs, and reviewing AI-assisted drafts. It "
        "runs on your computer and keeps generated artifacts separate from your "
        "original product documents."
    )
    st.markdown(
        """
1. **Create a product** with the context your team needs.
2. **Create a BRD or PRD** for that product.
3. Keep unfinished documents in **Draft** while they are still being reviewed.
4. Change a document to **Approved** only after a person has reviewed it.
5. Use the AI Assistant, which treats only Approved BRDs and PRDs as trusted sources.
6. Review the generated content and every citation back to its product, document, and section.
7. **Accept, revise, or reject** the generated draft. Revised content still requires an explicit acceptance.
"""
    )
    st.markdown("#### Draft, Approved, and trusted sources")
    st.write(
        "Draft means work is unfinished and may still be incorrect. Approved "
        "means a person has reviewed the document and considers it ready to use "
        "as evidence. Draft documents are excluded from AI retrieval so unfinished "
        "ideas do not silently become trusted context. Citations make the evidence "
        "visible and help you identify unsupported output, but they do not replace "
        "human judgment."
    )
    st.markdown("#### Human control and source protection")
    st.write(
        "AI-generated content is temporary until you explicitly accept it. You "
        "remain responsible for checking the result and its citations. Accepting "
        "content saves a separate artifact; it never edits or overwrites an "
        "original BRD or PRD."
    )
    st.markdown("#### Optional OpenAI setup")
    st.write(
        "AI features require your own OpenAI API key supplied through a secure "
        "local environment setting. Never type an API key into PMC source code or "
        "commit one to Git. Product and document management work without an API key."
    )

    st.markdown("#### Explore with fictional sample data")
    st.write(
        f"Optionally load {SAMPLE_PRODUCT_NAME}, one Approved fictional PRD, and "
        "one Draft fictional BRD. Nothing is loaded automatically, and your "
        "existing products and documents are never replaced."
    )
    st.caption(
        "To remove the sample later, open View Products, select the product whose "
        "name begins [Fictional Sample], and use Delete. Product deletion also "
        "removes that sample product's associated documents."
    )
    if not st.button(
        "Load fictional sample data",
        key="load_fictional_sample_data",
    ):
        return
    try:
        result = load_fictional_sample_data(APP_DATABASE_FILE)
    except (
        DatabaseSchemaError,
        ProductValidationError,
        DocumentValidationError,
        DocumentAssociationError,
        sqlite3.Error,
        RuntimeError,
    ):
        st.error(
            "Fictional sample data could not be loaded safely. Existing products "
            "and documents were not replaced. Please try again."
        )
        return
    if result.status is SampleDataLoadStatus.ALREADY_LOADED:
        st.info(
            f"{SAMPLE_PRODUCT_NAME} is already loaded. No duplicate sample was "
            "created."
        )
    else:
        st.success(
            f"{SAMPLE_PRODUCT_NAME} was loaded with one Approved PRD and one "
            "Draft BRD. Open View Products to explore it."
        )


def render_dashboard() -> None:
    """Render the approved product metrics."""

    st.header("Dashboard")
    st.write(
        "PMC is a local portfolio application showing how grounded AI can help "
        "Product Managers create and review Agile artifacts from Approved BRDs "
        "and PRDs without handing product decisions to AI."
    )
    st.caption(
        "Citations, source-freshness checks, claim-support assessment, human "
        "review, and explicit acceptance keep evidence and accountability visible."
    )
    render_getting_started()
    st.divider()

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
    render_accepted_artifact_history(product)
    render_accepted_agile_history(product)


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
    clear_stale_page_state(selected_section)

    st.title(APP_TITLE)
    st.caption("A focused workspace for product strategy and context.")

    renderers: dict[str, Callable[[], None]] = {
        "Dashboard": render_dashboard,
        "Create Product": render_create_product,
        "Create PRD": lambda: render_primary_document_creation(DocumentType.PRD),
        "Create BRD": lambda: render_primary_document_creation(DocumentType.BRD),
        "AI Assistant": render_ai_assistant,
        "View Products": render_view_products,
        "Search Products": render_search_products,
    }
    renderers[selected_section]()


if __name__ == "__main__":
    main()
