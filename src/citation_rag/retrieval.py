"""Phase 5: retrieve the most relevant Chunks for a natural-language query.

Concept:
    Query
      v
    Embedding vector (same model used for chunks — vectors must share a space)
      v
    Cosine similarity against every stored chunk vector
      v
    Sort by similarity, keep the top-K
      v
    Relevant chunks

Cosine similarity measures the angle between two vectors, not their length:

    cosine_similarity(a, b) = (a . b) / (||a|| * ||b||)

Two vectors pointing in the same direction score close to 1, regardless of
their magnitude. That is exactly what we want here: two chunks can be
"about the same thing" even if one embeds a short sentence and the other a
much longer paragraph.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from embeddings import EmbeddingProvider, load_embedded_chunks
from models import Chunk, EmbeddedChunk


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity between two vectors, in [-1, 1]."""
    vec_a = np.array(a)
    vec_b = np.array(b)
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def search(
    query: str,
    chunks: list[Chunk],
    embedded_chunks: list[EmbeddedChunk],
    provider: EmbeddingProvider,
    top_k: int = 5,
) -> list[tuple[Chunk, float]]:
    """Return the top_k (Chunk, similarity_score) pairs for a query, best first."""
    query_vector = provider.embed(query)

    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    scored = [
        (chunks_by_id[embedded.chunk_id], cosine_similarity(query_vector, embedded.embedding))
        for embedded in embedded_chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    return scored[:top_k]


def print_results(results: list[tuple[Chunk, float]]) -> None:
    """Print each result in a citation-friendly format for manual inspection."""
    for rank, (chunk, score) in enumerate(results, start=1):
        print(f"[{rank}] score={score:.4f}  {chunk.document_id}  "
              f"pages {chunk.page_start}-{chunk.page_end}  lines {chunk.line_start}-{chunk.line_end}")
        print(chunk.content)
        print()


# execution
if __name__ == "__main__":
    from embeddings import create_embedding_provider
    from providers import EmbeddingProviderName

    ROOT = Path(__file__).resolve().parents[2]
    cache_path = ROOT / "files" / "embeddings_cache.json"

    chunks, embedded_chunks = load_embedded_chunks(cache_path)
    provider = create_embedding_provider(EmbeddingProviderName.MONGO_VOYAGE)

    query = input("Ask a question: ")
    results = search(query, chunks, embedded_chunks, provider, top_k=5)
    print_results(results)
