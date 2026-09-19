"""Connector: chunk one or more PDFs, embed their chunks, and cache to disk.

This exists so documents are only chunked and embedded once. On later calls,
the cache file is loaded instead of re-parsing PDFs and re-calling the
embedding provider. Since each Chunk's chunk_id/document_id already carries
its source filename, chunks from different PDFs can safely share one cache.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from embeddings import create_embedding_provider, embed_chunks, load_embedded_chunks, save_embedded_chunks
from models import Chunk, EmbeddedChunk
from pdf_inspector import chunker, extract_document_model
from providers import EmbeddingProviderName


def build_chunk_embeddings(
    pdf_paths: list[str],
    cache_path: Path,
    provider_name: EmbeddingProviderName,
    chunk_size: int = 10,
) -> list[EmbeddedChunk]:
    """Return embedded chunks for one or more PDFs, reusing the cache if present."""
    if cache_path.exists():
        _, embedded_chunks = load_embedded_chunks(cache_path)
        return embedded_chunks

    all_chunks: list[Chunk] = []
    for pdf_path in pdf_paths:
        with pymupdf.open(pdf_path) as doc:
            doc_model = extract_document_model(doc)
        all_chunks.extend(chunker(doc_model, chunk_size=chunk_size))

    provider = create_embedding_provider(provider_name)
    embedded_chunks = embed_chunks(all_chunks, provider)
    save_embedded_chunks(all_chunks, embedded_chunks, cache_path)

    return embedded_chunks


def add_document(
    pdf_path: str,
    cache_path: Path,
    provider_name: EmbeddingProviderName,
    chunk_size: int = 10,
) -> list[EmbeddedChunk]:
    """Chunk + embed one new PDF and merge it into an existing cache.

    Unlike build_chunk_embeddings, this never re-embeds documents already in
    the cache — only the new PDF's chunks are sent to the embedding provider.
    """
    existing_chunks: list[Chunk] = []
    existing_embedded: list[EmbeddedChunk] = []
    if cache_path.exists():
        existing_chunks, existing_embedded = load_embedded_chunks(cache_path)

    document_id = Path(pdf_path).name
    if any(chunk.document_id == document_id for chunk in existing_chunks):
        return existing_embedded  # already ingested; skip re-embedding

    with pymupdf.open(pdf_path) as doc:
        doc_model = extract_document_model(doc)
    new_chunks = chunker(doc_model, chunk_size=chunk_size)

    provider = create_embedding_provider(provider_name)
    new_embedded = embed_chunks(new_chunks, provider)

    all_chunks = existing_chunks + new_chunks
    all_embedded = existing_embedded + new_embedded
    save_embedded_chunks(all_chunks, all_embedded, cache_path)

    return all_embedded



# execution
if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[2]
    prompting_pdf_path = str(ROOT / "files" / "prompting.pdf")
    author_pdf_path = str(ROOT / "files" / "Author.pdf")
    cache_path = ROOT / "files" / "embeddings_cache.json"

    result = build_chunk_embeddings(
        pdf_paths=[prompting_pdf_path, author_pdf_path],
        cache_path=cache_path,
        provider_name=EmbeddingProviderName.MONGO_VOYAGE,
    )

    print(f"Total embedded chunks: {len(result)}")
    print(f"Sample: {result[0].chunk_id}, vector length={len(result[0].embedding)}")


