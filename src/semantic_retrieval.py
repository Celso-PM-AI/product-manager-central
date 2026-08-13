"""Deterministic chunking and semantic retrieval for approved sources."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final, Protocol

from src.database import DATABASE_FILE, list_retrievable_document_sections
from src.models import DocumentStatus, DocumentType, RetrievableDocumentSection


DEFAULT_CHUNK_MAX_CHARACTERS: Final[int] = 1_200
DEFAULT_RESULT_LIMIT: Final[int] = 5
DEFAULT_MINIMUM_SIMILARITY: Final[float] = 0.0


class EmbeddingProvider(Protocol):
    """Replaceable ordered batch-embedding boundary."""

    def create_embeddings(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Return one vector for every supplied text, in the same order."""


@dataclass(frozen=True)
class RetrievalChunk:
    """Stable source text plus complete citation metadata."""

    chunk_id: str
    chunk_index: int
    text: str
    product_id: int
    product_name: str
    document_id: int
    document_title: str
    document_type: DocumentType
    document_status: DocumentStatus
    section_key: str
    section_title: str
    section_content_digest: str | None = None


@dataclass(frozen=True)
class SemanticRetrievalResult:
    """One ranked source chunk and its cosine similarity."""

    chunk: RetrievalChunk
    similarity: float


class SemanticRetrievalState(str, Enum):
    """Explicit semantic retrieval outcomes for future UI use."""

    RESULTS = "results"
    NO_APPROVED_SOURCES = "no_approved_sources"
    NO_RELEVANT_RESULTS = "no_relevant_results"


@dataclass(frozen=True)
class SemanticRetrievalResponse:
    """Ranked retrieval results with a clear empty-state message."""

    state: SemanticRetrievalState
    message: str
    results: tuple[SemanticRetrievalResult, ...]


def _split_long_text(text: str, maximum: int) -> list[str]:
    """Split oversized text at word boundaries, then hard boundaries."""

    parts: list[str] = []
    current = ""
    for word in text.split():
        if len(word) > maximum:
            if current:
                parts.append(current)
                current = ""
            parts.extend(
                word[offset : offset + maximum]
                for offset in range(0, len(word), maximum)
            )
        elif not current:
            current = word
        elif len(current) + 1 + len(word) <= maximum:
            current = f"{current} {word}"
        else:
            parts.append(current)
            current = word
    if current:
        parts.append(current)
    return parts


def _section_text_chunks(text: str, maximum: int) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text.strip())
        if paragraph.strip()
    ]
    units = [
        unit
        for paragraph in paragraphs
        for unit in (
            [paragraph]
            if len(paragraph) <= maximum
            else _split_long_text(paragraph, maximum)
        )
    ]
    chunks: list[str] = []
    current = ""
    for unit in units:
        separator = "\n\n" if current else ""
        if current and len(current) + len(separator) + len(unit) > maximum:
            chunks.append(current)
            current = unit
        else:
            current = f"{current}{separator}{unit}"
    if current:
        chunks.append(current)
    return chunks


def chunk_approved_sections(
    sections: Sequence[RetrievableDocumentSection],
    *,
    max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
) -> list[RetrievalChunk]:
    """Create repeatable paragraph-aware chunks from approved BRD/PRD sections."""

    if max_characters < 1:
        raise ValueError("Chunk size must be a positive integer.")

    chunks: list[RetrievalChunk] = []
    for section in sections:
        if (
            section.document_status is not DocumentStatus.APPROVED
            or section.document_type not in {DocumentType.BRD, DocumentType.PRD}
        ):
            continue
        for index, text in enumerate(
            _section_text_chunks(section.section_content, max_characters)
        ):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            chunks.append(
                RetrievalChunk(
                    chunk_id=(
                        f"document:{section.document_id}:section:"
                        f"{section.section_key}:chunk:{index}:{digest}"
                    ),
                    chunk_index=index,
                    text=text,
                    product_id=section.product_id,
                    product_name=section.product_name,
                    document_id=section.document_id,
                    document_title=section.document_title,
                    document_type=section.document_type,
                    document_status=section.document_status,
                    section_key=section.section_key,
                    section_title=section.section_title,
                    section_content_digest=hashlib.sha256(
                        section.section_content.encode("utf-8")
                    ).hexdigest(),
                )
            )
    return chunks


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Embedding vectors must be non-empty and have equal dimensions.")
    if not all(math.isfinite(value) for value in (*left, *right)):
        raise ValueError("Embedding vectors must contain only finite numbers.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


class SemanticRetriever:
    """Rank only currently approved source chunks using injected embeddings."""

    def __init__(
        self,
        source_loader: Callable[[], list[RetrievableDocumentSection]],
        embedding_provider: EmbeddingProvider,
        *,
        chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
        minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
    ) -> None:
        if not -1.0 <= minimum_similarity <= 1.0:
            raise ValueError("Minimum similarity must be between -1 and 1.")
        self._source_loader = source_loader
        self._embedding_provider = embedding_provider
        self._chunk_max_characters = chunk_max_characters
        self._minimum_similarity = minimum_similarity

    def _load_chunks(self) -> list[RetrievalChunk]:
        return chunk_approved_sections(
            self._source_loader(),
            max_characters=self._chunk_max_characters,
        )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> SemanticRetrievalResponse:
        """Return relevant chunks ranked by descending cosine similarity."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Semantic retrieval query cannot be empty.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("Semantic retrieval result limit must be positive.")

        chunks = self._load_chunks()
        if not chunks:
            return SemanticRetrievalResponse(
                SemanticRetrievalState.NO_APPROVED_SOURCES,
                "No approved BRD or PRD sources are available.",
                (),
            )

        vectors = self._embedding_provider.create_embeddings(
            [normalized_query, *(chunk.text for chunk in chunks)]
        )
        if len(vectors) != len(chunks) + 1:
            raise ValueError("Embedding provider returned an unexpected vector count.")

        current_chunks = {
            chunk.chunk_id: chunk for chunk in self._load_chunks()
        }
        ranked = [
            SemanticRetrievalResult(
                chunk=chunk,
                similarity=_cosine_similarity(vectors[0], vector),
            )
            for chunk, vector in zip(chunks, vectors[1:], strict=True)
            if current_chunks.get(chunk.chunk_id) == chunk
        ]
        ranked = [
            result
            for result in ranked
            if result.similarity >= self._minimum_similarity
        ]
        ranked.sort(key=lambda result: (-result.similarity, result.chunk.chunk_id))
        results = tuple(ranked[:limit])
        if not results:
            current_state = (
                SemanticRetrievalState.NO_RELEVANT_RESULTS
                if current_chunks
                else SemanticRetrievalState.NO_APPROVED_SOURCES
            )
            message = (
                "No relevant approved BRD or PRD sources were found."
                if current_chunks
                else "No approved BRD or PRD sources are available."
            )
            return SemanticRetrievalResponse(current_state, message, ())
        return SemanticRetrievalResponse(
            SemanticRetrievalState.RESULTS,
            f"Found {len(results)} relevant approved source chunk(s).",
            results,
        )


def retrieve_approved_sources(
    query: str,
    embedding_provider: EmbeddingProvider,
    database_path: str | Path = DATABASE_FILE,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
    chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
    minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
) -> SemanticRetrievalResponse:
    """Retrieve from the live approved-source boundary without modifying it."""

    retriever = SemanticRetriever(
        lambda: list_retrievable_document_sections(database_path),
        embedding_provider,
        chunk_max_characters=chunk_max_characters,
        minimum_similarity=minimum_similarity,
    )
    return retriever.retrieve(query, limit=limit)
