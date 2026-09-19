"""TASK 08: prove a Chunk's provenance fields resolve back to its real source lines."""

from pathlib import Path

import pymupdf
from models import Chunk
from pdf_inspector import chunker, extract_document_model

PDF_PATH = Path(__file__).resolve().parents[1] / "files" / "AiEngineering.pdf"


def test_chunk_provenance_resolves_to_original_lines():
    with pymupdf.open(PDF_PATH) as doc:
        document = extract_document_model(doc)

    page = document.pages[10]
    selected_lines = page.lines[0:3]

    chunk = Chunk(
        chunk_id="ai-engineering:chunk:0001",
        document_id="ai-engineering",
        content="\n".join(line.text for line in selected_lines),
        page_start=page.number,
        page_end=page.number,
        line_start=selected_lines[0].number,
        line_end=selected_lines[-1].number,
    )

    # Provenance means the chunk's line range alone must be enough to find the
    # exact source lines again, without knowing which page they live on.
    all_lines = [line for page in document.pages for line in page.lines]
    resolved_lines = [line for line in all_lines if chunk.line_start <= line.number <= chunk.line_end]

    assert [line.text for line in resolved_lines] == [line.text for line in selected_lines]
    assert chunk.content == "\n".join(line.text for line in resolved_lines)
    assert chunk.page_start == chunk.page_end == page.number


def test_page_spanning_chunk_resolves_to_original_lines():
    with pymupdf.open(PDF_PATH) as doc:
        document = extract_document_model(doc)

    chunks = chunker(document, chunk_size=10)
    chunk = next(c for c in chunks if c.page_start != c.page_end)

    # Same provenance check as above, but now the chunk must correctly span
    # two different PageModel entries instead of staying inside one page.
    all_lines = [line for page in document.pages for line in page.lines]
    resolved_lines = [line for line in all_lines if chunk.line_start <= line.number <= chunk.line_end]
    resolved_pages = {
        page.number
        for page in document.pages
        for line in page.lines
        if chunk.line_start <= line.number <= chunk.line_end
    }

    assert chunk.content == "\n".join(line.text for line in resolved_lines)
    assert resolved_pages == {chunk.page_start, chunk.page_end}
