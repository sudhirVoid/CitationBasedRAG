"""Provenance-preserving document model built from PDF parser output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Line:
    """One logical line of text with its document-wide line number and position."""

    number: int
    text: str
    bbox: tuple[float, float, float, float]


@dataclass
class PageModel:
    """One page with its full text and the logical lines found on it."""

    number: int
    text: str
    lines: list[Line] = field(default_factory=list)


@dataclass
class DocumentModel:
    """A parsed PDF: its source file and the pages that carry its provenance.

    Named DocumentModel/PageModel to avoid clashing with pymupdf.Document/Page.
    """

    source: str | None
    pages: list[PageModel] = field(default_factory=list)


@dataclass
class PageHighlight:
    """A bounding box on one page, used to visually locate part of a Chunk."""

    page: int
    bbox: tuple[float, float, float, float]


@dataclass
class Chunk:
    """A retrievable unit of text that always points back to its source lines."""

    chunk_id: str
    document_id: str
    content: str
    page_start: int
    page_end: int
    line_start: int
    line_end: int
    highlights: list[PageHighlight] = field(default_factory=list)

@dataclass
class EmbeddedChunk:
    """A Chunk with its embedding vector for similarity-based retrieval."""

    chunk_id: str
    embedding: list[float]