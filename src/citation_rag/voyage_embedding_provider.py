"""Voyage AI (via MongoDB Atlas) implementation of EmbeddingProvider."""

from __future__ import annotations

import os

import voyageai
from dotenv import load_dotenv
from embeddings import EmbeddingProvider

DEFAULT_MODEL = "voyage-4-large"


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Calls Voyage AI's embed() via the official voyageai SDK."""

    def __init__(self) -> None:
        load_dotenv()  # reads .env into os.environ if present; never overwrites real env vars
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY environment variable is not set. "
                "Store the model API key there — never hardcode it."
            )
        self._client = voyageai.Client(api_key=api_key, max_retries=3, timeout=30)
        self._model = os.environ.get("VOYAGE_MODEL", DEFAULT_MODEL)

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text."""
        result = self._client.embed(texts=[text], model=self._model)
        return result.embeddings[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text, in a single batched call."""
        result = self._client.embed(texts=texts, model=self._model)
        return result.embeddings

