# Architecture: How Citation-Aware RAG Works Here

This document explains what we built and, most importantly, **how a citation
survives the entire pipeline** — from raw PDF bytes to a clickable `[1]` in
the browser that highlights the exact source text.

---

## 1. The core idea: provenance never gets thrown away

Every stage of this pipeline takes a piece of data and produces a **new**
piece of data that is *richer*, never *poorer*, in location metadata:

```text
PDF bytes
   │  (PyMuPDF parses structure: blocks → lines → spans, each with a bbox)
   ▼
DocumentModel (pages, lines, each line has: number, text, bbox)
   │  (chunker groups consecutive lines; unions their bboxes per page)
   ▼
Chunk (content, document_id, page_start/end, line_start/end, highlights[])
   │  (embedding provider turns chunk.content into a vector)
   ▼
EmbeddedChunk (chunk_id, embedding vector) — paired with Chunk, never replacing it
   │  (cosine similarity search against a query vector)
   ▼
Retrieved (Chunk, score) pairs
   │  (context builder assigns temporary SOURCE_N labels)
   ▼
Context string ("SOURCE_1\nFile:...\nPage:...\n\n<content>") + source_map
   │  (LLM generates an answer, citing [SOURCE_N])
   ▼
Raw answer text containing [SOURCE_1], [SOURCE_2]...
   │  (citation resolver looks up SOURCE_N in source_map — never trusts the LLM)
   ▼
Final answer with [1], [2]... + structured citations (document, page, line, bbox)
   │  (frontend renders citations as clickable badges)
   ▼
Click → load PDF page → draw highlight box at the real bbox → scroll into view
```

The rule that makes citations trustworthy: **the LLM never invents or sees
real location metadata.** It only ever sees an opaque label like
`SOURCE_1`. The application (not the model) is the single source of truth
for where that label actually points.

---

## 2. The data models (`models.py`)

Four dataclasses, each one layer of the pipeline above:

```python
@dataclass
class Line:
    number: int                                   # document-wide, not PDF-native
    text: str
    bbox: tuple[float, float, float, float]        # exact position on the page

@dataclass
class PageModel:
    number: int
    text: str
    lines: list[Line]

@dataclass
class DocumentModel:
    source: str | None                             # original filename
    pages: list[PageModel]

@dataclass
class PageHighlight:
    page: int
    bbox: tuple[float, float, float, float]        # union bbox for one page

@dataclass
class Chunk:
    chunk_id: str          # "{document}:chunk:0001" — deterministic, not random
    document_id: str       # the original filename — this IS the citation's "File:"
    content: str           # the actual text sent to the embedding model + LLM
    page_start: int
    page_end: int
    line_start: int
    line_end: int
    highlights: list[PageHighlight]   # one bbox per page the chunk touches

@dataclass
class EmbeddedChunk:
    chunk_id: str           # links back to a Chunk — never duplicates its content
    embedding: list[float]  # the vector; kept separate from Chunk on purpose
```

### Why `Line.number` is document-wide, not per-page

PyMuPDF gives **no line numbers at all** — only nested blocks/lines/spans
per page. We invented a single counter that increments across the *entire*
document (page 1's lines don't reset before page 2's). This is what lets a
`Chunk`'s `line_start`/`line_end` uniquely identify its source lines without
also needing to know which page they're on — the numbers alone are enough
to trace back to the exact text (proven in `tests/test_chunk_provenance.py`).

### Why `Chunk` and `EmbeddedChunk` are separate classes

`Chunk` is produced during **chunking** (a text/provenance concept).
`EmbeddedChunk` is produced during **embedding** (a numeric-vector concept).
Per AGENT.MD's "keep phases separate" principle, a `Chunk` is meaningful
*before* any embedding model ever runs, so we didn't bolt a `vector` field
onto it. Instead `EmbeddedChunk` just holds `chunk_id` + `embedding`, and the
two are paired back together (via `chunk_id`) wherever both are needed — see
`embeddings.load_embedded_chunks()`.

### Why `Chunk` has no single `bbox`, only `highlights: list[PageHighlight]`

A chunk can span a page boundary (its lines come from the end of page 11 and
the start of page 12). A single bbox can't represent two disjoint regions on
two different pages. `PageHighlight` records `(page, bbox)` per page the
chunk actually touches, computed in `chunker()` by unioning the bboxes of
every line that landed on that page:

```python
bbox = (min(x0), min(y0), max(x1), max(y1))  # over all lines on that page
```

---

## 3. How chunking preserves and extends provenance (`pdf_inspector.py`)

```python
def chunker(doc_model, chunk_size):
    flat_lines = [(page.number, line) for page in doc_model.pages for line in page.lines]
    ...
    for i in range(0, len(flat_lines), chunk_size):
        group = flat_lines[i : i + chunk_size]
        ...
```

Lines are **flattened across the whole document first**, then sliced into
fixed-size groups. This is deliberate: if chunking only grouped lines
*within* a single page, a chunk could never continue a sentence that runs
onto the next page. Flattening first lets a chunk's `page_start` and
`page_end` legitimately differ — proven by
`tests/test_chunk_provenance.py::test_page_spanning_chunk_resolves_to_original_lines`.

`chunk_id` is deterministic, not random: `f"{document_id}:chunk:{n:04d}"`.
This matters for two reasons:
1. It's human-readable while debugging (`AiEngineering.pdf:chunk:0016`).
2. Re-running the pipeline on the same document produces the same IDs,
   which is what lets the JSON cache be diffed/inspected reliably.

---

## 4. Embeddings are cached, never recomputed (`embeddings.py`, `pipeline.py`)

Two functions do all the persistence work:

```python
def save_embedded_chunks(chunks, embedded_chunks, path):
    # Merges each Chunk's fields with its matching embedding into one JSON
    # record per chunk — provenance and vector travel together on disk.
    ...

def load_embedded_chunks(path) -> tuple[list[Chunk], list[EmbeddedChunk]]:
    # Reconstructs real Chunk/EmbeddedChunk/PageHighlight objects from JSON
    # (JSON only knows plain dicts/lists, not our dataclasses).
    ...
```

`pipeline.build_chunk_embeddings()` builds the cache from scratch (skips
work entirely if the cache file already exists). `pipeline.add_document()`
is the incremental version: it loads whatever's already cached, chunks +
embeds *only* the new PDF, and merges — so uploading a second document
never re-embeds (and re-pays for) documents already processed. It also
refuses to re-ingest a `document_id` already present, to avoid silent
duplicates.

---

## 5. Retrieval: cosine similarity from first principles (`retrieval.py`)

```python
def cosine_similarity(a, b):
    vec_a, vec_b = np.array(a), np.array(b)
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))
```

Implemented directly with NumPy rather than pulled from a vector-database
library, per AGENT.MD's "understand the primitive before using an
abstraction" rule. `search()` embeds the query with the *same* model used
for the chunks (mixing models would compare vectors from two different,
incompatible spaces — meaningless), scores every cached chunk, and returns
the top-K `(Chunk, score)` pairs.

---

## 6. Context building: the LLM never sees real metadata (`context_builder.py`)

```python
def build_context(results):
    for rank, (chunk, _score) in enumerate(results, start=1):
        source_id = f"SOURCE_{rank}"
        source_map[source_id] = chunk          # kept by us, not sent to the LLM as "truth"
        blocks.append(f"{source_id}\nFile: {chunk.document_id}\nPage: ...\n\n{chunk.content}")
    return "\n\n".join(blocks), source_map
```

The LLM prompt *shows* `File:`/`Page:`/`Lines:` as readable context, but the
`source_map` — not the LLM's output — is what the application trusts when
resolving a citation afterward. This is the direct implementation of
AGENT.MD section 15:

```text
Retrieved Chunk → content + source_id + document + page + location → LLM → [SOURCE_1]
                                                                              │
                                                                              ▼
                                                          Application resolves (not the LLM)
```

---

## 7. Citation resolution: how `[SOURCE_N]` becomes a real, safe citation (`citation.py`)

This is the crux of "attaining citations":

```python
SOURCE_PATTERN = re.compile(r"[\[\u3010]SOURCE_(\d+)[\]\u3011]")

def extract_citations(answer, source_map):
    used_source_ids = []

    def replace(match):
        source_id = f"SOURCE_{match.group(1)}"
        if source_id not in source_map:
            return ""                     # <-- hallucinated citation: dropped, not resolved
        if source_id not in used_source_ids:
            used_source_ids.append(source_id)
        return f"[{used_source_ids.index(source_id) + 1}]"

    resolved_answer = SOURCE_PATTERN.sub(replace, answer)

    citations = [
        {
            "number": i,
            "document_id": source_map[sid].document_id,
            "page_start": source_map[sid].page_start,
            "page_end": source_map[sid].page_end,
            "line_start": source_map[sid].line_start,
            "line_end": source_map[sid].line_end,
            "highlights": [{"page": h.page, "bbox": list(h.bbox)} for h in source_map[sid].highlights],
            "content": source_map[sid].content,
        }
        for i, sid in enumerate(used_source_ids, start=1)
    ]
    return resolved_answer, citations
```

Three important properties:

1. **Renumbering.** The LLM might cite `SOURCE_3` before `SOURCE_1` in the
   text, or skip `SOURCE_2` entirely. We renumber to `[1]`, `[2]`... in the
   order citations actually *appear*, not the order they were retrieved.
2. **Hallucination safety.** If the LLM invents `SOURCE_99` (a label that
   was never in `source_map`), `replace()` returns `""` — the fake citation
   is silently removed from the answer rather than being "resolved" into a
   fake-looking real reference. This was verified directly in testing.
3. **Bracket-style tolerance.** In practice, the LLM (Groq's
   `openai/gpt-oss-20b`) sometimes emitted full-width brackets `【SOURCE_1】`
   instead of ASCII `[SOURCE_1]`. The regex matches both, so a citation
   never silently fails to resolve just because of a stylistic quirk in the
   model's output. The prompt (`generation.py`) was also tightened to
   explicitly demand ASCII brackets, to reduce how often this happens.

`resolve_citations()` (used by the CLI) wraps `extract_citations()` and
appends a plain-text reference list. `qa.answer_question_structured()` (used
by the web API) returns the JSON-friendly version directly — `{"answer":
..., "citations": [...]}` — so the frontend can render clickable elements
instead of parsing text.

---

## 8. From citation to highlighted PDF (frontend + `/pdf/{document_id}`)

The final leg of the journey:

```text
citation.highlights = [{"page": 11, "bbox": [x0, y0, x1, y1]}, {"page": 12, "bbox": [...]}]
        │
        ▼
Frontend loads the PDF via GET /pdf/{document_id} (PDF.js)
        │
        ▼
Renders the first highlighted page onto a <canvas> at a fixed scale
        │
        ▼
Overlay <div> positioned at (bbox * scale), sized to (width * scale, height * scale)
        │
        ▼
scrollIntoView() brings the highlight into view
```

One subtlety worth remembering: **PyMuPDF's bboxes are already top-left
origin, y-down** — the same orientation as canvas pixels — unlike the raw
PDF spec (bottom-left origin). That's why the frontend only *scales* the
bbox coordinates by the render scale; it does not need to flip the Y axis.

---

## 9. What this buys us, end to end

Ask "How does sampling affect a model's output?" and the system can answer:

```text
Sampling determines which token a model emits from all possible outputs... [1]

[1] prompting.pdf
    Page 1-2
    Lines 21-30
```

— where `[1]` is clickable, jumps to the exact page in `prompting.pdf`, and
draws an orange box around the exact lines the answer was grounded in. Every
number in that citation traces back, unbroken, to a `Line.bbox` that
PyMuPDF originally reported for that exact piece of text — nothing in
between (chunking, embedding, retrieval, or the LLM) was allowed to lose or
corrupt that location.
