"""End-to-end: question -> retrieval -> grounded LLM answer -> resolved citations."""

from __future__ import annotations

from pathlib import Path

from citation import extract_citations, resolve_citations
from context_builder import build_context
from embeddings import create_embedding_provider, load_embedded_chunks
from generation import build_grounded_prompt, create_llm_provider
from models import Chunk
from providers import EmbeddingProviderName, LLMProviderName
from retrieval import search


def _ask(
    question: str,
    cache_path: Path,
    embedding_provider_name: EmbeddingProviderName,
    llm_provider_name: LLMProviderName,
    top_k: int,
) -> tuple[str, dict[str, Chunk]]:
    """Run retrieval + generation, returning the LLM's raw answer + source_map."""
    chunks, embedded_chunks = load_embedded_chunks(cache_path)
    embedding_provider = create_embedding_provider(embedding_provider_name)

    results = search(question, chunks, embedded_chunks, embedding_provider, top_k=top_k)
    context, source_map = build_context(results)

    llm_provider = create_llm_provider(llm_provider_name)
    prompt = build_grounded_prompt(question, context)
    raw_answer = llm_provider.generate(prompt)

    return raw_answer, source_map


def answer_question(
    question: str,
    cache_path: Path,
    embedding_provider_name: EmbeddingProviderName,
    llm_provider_name: LLMProviderName,
    top_k: int = 5,
) -> str:
    """Return a grounded answer as plain text, with citations resolved inline."""
    raw_answer, source_map = _ask(question, cache_path, embedding_provider_name, llm_provider_name, top_k)
    return resolve_citations(raw_answer, source_map)


def answer_question_structured(
    question: str,
    cache_path: Path,
    embedding_provider_name: EmbeddingProviderName,
    llm_provider_name: LLMProviderName,
    top_k: int = 5,
) -> dict:
    """Return {"answer": str, "citations": [...]} for a UI to render and highlight."""
    raw_answer, source_map = _ask(question, cache_path, embedding_provider_name, llm_provider_name, top_k)
    resolved_answer, citations = extract_citations(raw_answer, source_map)
    return {"answer": resolved_answer, "citations": citations}


# execution
if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[2]
    cache_path = ROOT / "files" / "embeddings_cache.json"

    question = input("Ask a question: ")
    answer = answer_question(
        question,
        cache_path=cache_path,
        embedding_provider_name=EmbeddingProviderName.MONGO_VOYAGE,
        llm_provider_name=LLMProviderName.GROQ,
    )
    print(answer)
