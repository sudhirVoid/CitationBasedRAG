"""Phase 6: build a deterministic, citation-friendly context block for the LLM.

Concept:
    Retrieved chunks (Chunk, score) pairs
      v
    Assign each a temporary SOURCE_N label
      v
    Format: SOURCE_N / file / page / lines / content
      v
    Context string handed to the LLM + a source_id -> Chunk map kept by us

The LLM only ever sees "SOURCE_1", "SOURCE_2", etc. It never sees or invents
page/line numbers itself — the application is the only source of truth for
where a citation actually points (see AGENT.MD section 15).
"""

from __future__ import annotations

from models import Chunk


def build_context(results: list[tuple[Chunk, float]]) -> tuple[str, dict[str, Chunk]]:
    """Return (context_text, source_id -> Chunk map) for the retrieved chunks."""
    blocks = []
    source_map: dict[str, Chunk] = {}

    for rank, (chunk, _score) in enumerate(results, start=1):
        source_id = f"SOURCE_{rank}"
        source_map[source_id] = chunk
        blocks.append(
            f"{source_id}\n"
            f"File: {chunk.document_id}\n"
            f"Page: {chunk.page_start}-{chunk.page_end}\n"
            f"Lines: {chunk.line_start}-{chunk.line_end}\n\n"
            f"{chunk.content}"
        )

    return "\n\n".join(blocks), source_map
