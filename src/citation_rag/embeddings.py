"""Phase 4: turn Chunk text into embeddings for similarity-based retrieval."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path

from models import Chunk, EmbeddedChunk, PageHighlight
from providers import EmbeddingProviderName

# Concept:
# An embedding is a vector of numbers that represents the meaning of a piece
# of text. Texts with similar meaning end up with vectors that are close
# together in that vector space. This is what lets us search by meaning
# instead of exact keyword matches:
#
#   Query
#     v
#   Embedding vector
#     v
#   Distance / similarity
#     v
#   Nearest vectors
#     v
#   Relevant chunks
#
# LEARNED:
# A single number inside an embedding means nothing on its own, the same way
# one coordinate of a 2D point doesn't tell you a location. Meaning only
# exists in the full vector together, as a position in a high-dimensional
# space. Two chunks are "similar" when their whole vectors point toward the
# same region of that space, not because any individual number matches.
#
# LEARNED:
# The embedding provider is Voyage AI (via MongoDB Atlas), decided after
# weighing a local model vs. a hosted API. The rest of the program should
# depend on an abstract EmbeddingProvider, not on Voyage AI directly, so a
# different provider can be swapped in later without touching call sites.


class EmbeddingProvider(ABC):
    """Anything that can turn text into an embedding vector."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text."""

    @abstractmethod
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text, in one batched call."""


# LEARNED:
# VoyageEmbeddingProvider (in voyage_embedding_provider.py) implements this
# interface, and create_embedding_provider() is the only place that knows
# about it. Every other module calls create_embedding_provider(...).embed(),
# never VoyageEmbeddingProvider directly — swapping providers later means
# changing this factory only.


def create_embedding_provider(name: EmbeddingProviderName) -> EmbeddingProvider:
    """Factory: build the EmbeddingProvider matching `name`."""
    if name == EmbeddingProviderName.MONGO_VOYAGE:
        from voyage_embedding_provider import VoyageEmbeddingProvider
        return VoyageEmbeddingProvider()
    raise NotImplementedError


def embed_chunks(
    chunks: list[Chunk],
    provider: EmbeddingProvider,
    batch_size: int = 20,
    seconds_between_batches: float = 21.0,
) -> list[EmbeddedChunk]:
    """Embed chunks in batches to stay within the provider's rate limit.

    Free-tier Voyage AI accounts (no payment method) allow only 3 requests
    per minute, so batching many chunks per request and pacing requests
    ~20s apart avoids RateLimitError instead of retrying after failure.
    """
    embedded_chunks = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        vectors = provider.embed_many([chunk.content for chunk in batch])
        embedded_chunks.extend(
            EmbeddedChunk(chunk_id=chunk.chunk_id, embedding=vector)
            for chunk, vector in zip(batch, vectors)
        )

        is_last_batch = i + batch_size >= len(chunks)
        if not is_last_batch:
            time.sleep(seconds_between_batches)

    return embedded_chunks


def save_embedded_chunks(chunks: list[Chunk], embedded_chunks: list[EmbeddedChunk], path: Path) -> None:
    """Persist chunks + their embeddings together so chunking/embedding isn't repeated."""
    vectors_by_id = {e.chunk_id: e.embedding for e in embedded_chunks}
    records = [{**asdict(chunk), "embedding": vectors_by_id[chunk.chunk_id]} for chunk in chunks]
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def load_embedded_chunks(path: Path) -> tuple[list[Chunk], list[EmbeddedChunk]]:
    """Load previously saved chunks + embeddings back from disk."""
    records = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    embedded_chunks = []
    for record in records:
        embedding = record.pop("embedding")
        # JSON gives plain dicts/lists; rebuild PageHighlight dataclasses and
        # tuple bboxes so callers get real Chunk objects, not raw JSON shapes.
        record["highlights"] = [
            PageHighlight(page=h["page"], bbox=tuple(h["bbox"]))
            for h in record.get("highlights", [])
        ]
        chunk = Chunk(**record)
        chunks.append(chunk)
        embedded_chunks.append(EmbeddedChunk(chunk_id=chunk.chunk_id, embedding=embedding))
    return chunks, embedded_chunks

