"""Inspect PDF structure and preserve page-level provenance."""

from __future__ import annotations

import pymupdf

from models import Chunk, DocumentModel, Line, PageHighlight, PageModel


def normalize_pdf_page(document):
    # Keep text and source location together before chunking or retrieval.
    """Return explicit page records with text and source metadata."""
    source = document.name.split("\\")[-1] if hasattr(document, "name") else None
    return [
        {
            "page": page_number,
            "text": page.get_text("text"),
            "blocks": page.get_text("blocks"),
            "source": source,
        }
        for page_number, page in enumerate(document, start=1)
    ]


def extract_document_model(document) -> DocumentModel:
    """Return the document as DocumentModel/PageModel/Line records with full provenance."""
    source = document.name.split("\\")[-1] if hasattr(document, "name") else None
    doc_model = DocumentModel(source=source)
    line_number = 1

    for page_number, page in enumerate(document, start=1):
        page_model = PageModel(number=page_number, text=page.get_text("text"))
        doc_model.pages.append(page_model)

        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    continue
                page_model.lines.append(Line(number=line_number, text=text, bbox=line["bbox"]))
                line_number += 1

    return doc_model

def chunker(doc_model: DocumentModel, chunk_size: int) -> list[Chunk]:
    """Group every chunk_size consecutive lines into a Chunk, spanning page boundaries."""
    # Flatten first so a chunk can pick up where the previous page left off,
    # instead of restarting at every page break.
    flat_lines = [(page.number, line) for page in doc_model.pages for line in page.lines]
    document_id = doc_model.source or "unknown"

    chunks = []
    for i in range(0, len(flat_lines), chunk_size):
        group = flat_lines[i:i + chunk_size]
        pages_in_group = [page_number for page_number, _ in group]
        lines_in_group = [line for _, line in group]

        # Union each page's line bboxes into one highlight box per page, so a
        # chunk spanning pages gets a separate highlight for each page it touches.
        bboxes_by_page: dict[int, list[tuple[float, float, float, float]]] = {}
        for page_number, line in group:
            bboxes_by_page.setdefault(page_number, []).append(line.bbox)

        highlights = [
            PageHighlight(
                page=page_number,
                bbox=(
                    min(b[0] for b in boxes),
                    min(b[1] for b in boxes),
                    max(b[2] for b in boxes),
                    max(b[3] for b in boxes),
                ),
            )
            for page_number, boxes in bboxes_by_page.items()
        ]

        chunks.append(Chunk(
            chunk_id=f"{document_id}:chunk:{len(chunks) + 1:04d}",
            document_id=document_id,
            content="\n".join(line.text for line in lines_in_group),
            page_start=pages_in_group[0],
            page_end=pages_in_group[-1],
            line_start=lines_in_group[0].number,
            line_end=lines_in_group[-1].number,
            highlights=highlights,
        ))

    return chunks


def inspect_pdf_structure(pdf_path: str):
    """Print one normalized page and line record for inspection."""
    with pymupdf.open(pdf_path) as doc:
        normalized_pages = normalize_pdf_page(doc)

    with pymupdf.open(pdf_path) as doc:
        doc_model = extract_document_model(doc)

        _ = chunker(doc_model, chunk_size=10)


# LEARNED:
# A Chunk never stores its own bbox list; it stays traceable to its source
# through document_id, page_start/page_end, and line_start/line_end alone.
# Flattening lines across the whole document before chunking lets a chunk
# span a page boundary instead of always cutting off at the last page line.
# tests/test_chunk_provenance.py proves both single-page and page-spanning
# chunks resolve back to the correct original lines.
#
# Chunking (Phase 3) is functional; chunk_size experiments were skipped for
# now. Phase 4 (embeddings) continues in embeddings.py.


# execution
if __name__ == "__main__":
    #pdf_path = r"c:\Users\bhandars\source\repos\PracticeProjects\CitationBasedRAG\files\AiEngineering.pdf"
    prompting_pdf_path = r"c:\Users\bhandars\source\repos\PracticeProjects\CitationBasedRAG\files\prompting.pdf"
    author_pdf_path = r"c:\Users\bhandars\source\repos\PracticeProjects\CitationBasedRAG\files\Author.pdf"
    inspect_pdf_structure(prompting_pdf_path)