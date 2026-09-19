"""Identifiers for supported embedding/LLM providers, used by their factories."""

from __future__ import annotations

from enum import Enum


class EmbeddingProviderName(Enum):
    """Which embedding provider create_embedding_provider() should build."""

    MONGO_VOYAGE = "mongo_voyage"


class LLMProviderName(Enum):
    """Which LLM provider create_llm_provider() should build."""

    GROQ = "groq"
