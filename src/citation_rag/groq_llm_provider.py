"""Groq (OpenAI-compatible API) implementation of LLMProvider."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from generation import LLMProvider
from openai import OpenAI

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class GroqLLMProvider(LLMProvider):
    """Calls Groq's OpenAI-compatible responses API to generate text."""

    def __init__(self) -> None:
        load_dotenv()  # reads .env into os.environ if present; never overwrites real env vars
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set. "
                "Store the API key there — never hardcode it."
            )
        self._client = OpenAI(api_key=api_key, base_url=os.environ.get("GROQ_BASE_URL", DEFAULT_BASE_URL))
        self._model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    def generate(self, prompt: str) -> str:
        """Return the model's text completion for a prompt."""
        response = self._client.responses.create(input=prompt, model=self._model)
        return response.output_text
