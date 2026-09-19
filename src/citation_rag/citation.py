"""Phase 8: resolve [SOURCE_N] labels in an LLM answer back to real citations.

Concept:
    LLM answer containing [SOURCE_1], [SOURCE_2], ...
      v
    Find which SOURCE_N labels were actually used
      v
    Look each one up in the source_map (never trust the LLM's own claims
    about page/line numbers — only the application's source_map is truth)
      v
    Replace labels with [1], [2], ... and append a resolved reference list

Invalid citations (a SOURCE_N the LLM invented that isn't in source_map) are
dropped rather than resolved, so a hallucinated citation never reaches the
final answer as if it were real.
"""

from __future__ import annotations

import re

from models import Chunk

# Some LLMs stylistically substitute full-width brackets (【】) for ASCII
# square brackets even when told to use "[SOURCE_N]" — match both so a citation
# isn't silently dropped just because of bracket style.
SOURCE_PATTERN = re.compile(r"[\[\u3010]SOURCE_(\d+)[\]\u3011]")


def extract_citations(answer: str, source_map: dict[str, Chunk]) -> tuple[str, list[dict]]:
    """Replace [SOURCE_N] labels with [1], [2]... and return structured citation data.

    Each citation dict carries page/line/bbox info so a UI can jump straight
    to and highlight the exact source location — not just print it as text.
    """
    used_source_ids: list[str] = []

    def replace(match: re.Match) -> str:
        source_id = f"SOURCE_{match.group(1)}"
        if source_id not in source_map:
            return ""  # drop citations to sources that don't exist
        if source_id not in used_source_ids:
            used_source_ids.append(source_id)
        return f"[{used_source_ids.index(source_id) + 1}]"

    resolved_answer = SOURCE_PATTERN.sub(replace, answer)

    citations = [
        {
            "number": i,
            "document_id": source_map[source_id].document_id,
            "page_start": source_map[source_id].page_start,
            "page_end": source_map[source_id].page_end,
            "line_start": source_map[source_id].line_start,
            "line_end": source_map[source_id].line_end,
            "highlights": [
                {"page": h.page, "bbox": list(h.bbox)} for h in source_map[source_id].highlights
            ],
            "content": source_map[source_id].content,
        }
        for i, source_id in enumerate(used_source_ids, start=1)
    ]

    return resolved_answer, citations


def resolve_citations(answer: str, source_map: dict[str, Chunk]) -> str:
    """Replace [SOURCE_N] labels with numbered citations and append references."""
    resolved_answer, citations = extract_citations(answer, source_map)
    if not citations:
        return resolved_answer

    references = "\n\n".join(
        f"[{c['number']}] {c['document_id']}\n"
        f"    Page {c['page_start']}-{c['page_end']}\n"
        f"    Lines {c['line_start']}-{c['line_end']}"
        for c in citations
    )

    return f"{resolved_answer}\n\n{references}"

