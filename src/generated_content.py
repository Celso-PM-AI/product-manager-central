"""Human review and explicit acceptance for grounded generated content."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from secrets import token_urlsafe
from typing import Callable, Final

from src.database import (
    DATABASE_FILE,
    GeneratedArtifactValidationError,
    get_product,
    save_accepted_generated_artifact,
)
from src.grounded_generation import GenerationCitation, GroundedGenerationResult
from src.models import GeneratedArtifact


MAX_ACCEPTED_CONTENT_CHARACTERS: Final[int] = 50_000


class ReviewValidationError(ValueError):
    """Raised when a review action is incomplete or no longer valid."""


class ReviewDecision(str, Enum):
    """Explicit human-review states; only accepted content is persisted."""

    PENDING = "pending"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


@dataclass(frozen=True)
class GeneratedContentReview:
    """In-memory review preserving original AI output and human revision."""

    review_key: str
    product_id: int
    request: str
    original_content: str
    citations: tuple[GenerationCitation, ...]
    revised_content: str | None = None
    decision: ReviewDecision = ReviewDecision.PENDING
    saved_artifact_id: int | None = None

    @property
    def content_for_acceptance(self) -> str:
        return self.revised_content or self.original_content

    @property
    def was_revised(self) -> bool:
        return self.revised_content is not None


@dataclass(frozen=True)
class AcceptanceResult:
    """Accepted review plus whether this action created a new database row."""

    review: GeneratedContentReview
    artifact: GeneratedArtifact
    created: bool


def _normalized_review_content(content: object) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ReviewValidationError("Reviewed content cannot be empty.")
    normalized = content.strip()
    if len(normalized) > MAX_ACCEPTED_CONTENT_CHARACTERS:
        raise ReviewValidationError(
            "Reviewed content must be 50,000 characters or fewer."
        )
    return normalized


class GeneratedContentReviewService:
    """Keep review separate from generation and persist only explicit acceptance."""

    def __init__(
        self,
        database_path: str | Path = DATABASE_FILE,
        *,
        key_factory: Callable[[], str] | None = None,
    ) -> None:
        self._database_path = database_path
        self._key_factory = key_factory or (lambda: token_urlsafe(24))

    def begin_review(
        self,
        *,
        product_id: int,
        request: object,
        generation: GroundedGenerationResult,
    ) -> GeneratedContentReview:
        """Create an unsaved pending review from grounded generated output."""

        if get_product(product_id, self._database_path) is None:
            raise ReviewValidationError(
                "Select an available product before generating content."
            )
        if not isinstance(request, str) or not request.strip():
            raise ReviewValidationError("Enter a request before starting review.")
        if (
            not generation.grounded
            or not generation.is_generated_draft
            or not generation.requires_human_review
            or generation.explicitly_accepted
            or generation.can_save
            or not generation.content
            or not generation.citations
        ):
            raise ReviewValidationError(
                "Only grounded, unaccepted generated content can enter review."
            )
        review_key = self._key_factory().strip()
        if not review_key:
            raise ReviewValidationError("A review identifier could not be created.")
        return GeneratedContentReview(
            review_key=review_key,
            product_id=product_id,
            request=request.strip(),
            original_content=_normalized_review_content(generation.content),
            citations=generation.citations,
        )

    def revise(
        self,
        review: GeneratedContentReview,
        revised_content: object,
    ) -> GeneratedContentReview:
        """Record a human revision while keeping the review pending and unsaved."""

        self._require_pending(review)
        normalized = _normalized_review_content(revised_content)
        return replace(
            review,
            revised_content=(
                None if normalized == review.original_content else normalized
            ),
        )

    def reject(self, review: GeneratedContentReview) -> GeneratedContentReview:
        """Reject without writing an approved or saved artifact."""

        self._require_pending(review)
        return replace(review, decision=ReviewDecision.REJECTED)

    def accept(self, review: GeneratedContentReview) -> AcceptanceResult:
        """Persist only this explicit human acceptance action."""

        self._require_pending(review)
        accepted_content = _normalized_review_content(review.content_for_acceptance)
        citation_rows = tuple(
            {
                "source_number": citation.source_number,
                "source_product_id": citation.product_id,
                "source_product_name": citation.product,
                "document_id": citation.document_id,
                "document_title": citation.document_title,
                "document_type": citation.document_type,
                "section_key": citation.section_key,
                "section_title": citation.section,
            }
            for citation in review.citations
        )
        try:
            artifact, created = save_accepted_generated_artifact(
                acceptance_key=review.review_key,
                product_id=review.product_id,
                request=review.request,
                original_content=review.original_content,
                accepted_content=accepted_content,
                citations=citation_rows,
                database_path=self._database_path,
            )
        except GeneratedArtifactValidationError as error:
            raise ReviewValidationError(str(error)) from error
        accepted_review = replace(
            review,
            decision=ReviewDecision.ACCEPTED,
            saved_artifact_id=artifact.id,
        )
        return AcceptanceResult(accepted_review, artifact, created)

    @staticmethod
    def _require_pending(review: GeneratedContentReview) -> None:
        if review.decision is not ReviewDecision.PENDING:
            raise ReviewValidationError(
                "This review is already complete and cannot be changed."
            )
