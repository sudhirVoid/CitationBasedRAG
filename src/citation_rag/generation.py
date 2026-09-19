"""Phase 7: send retrieved evidence to an LLM and get a grounded answer.

Concept:
    Context (SOURCE_1..N blocks) + user question
      v
    Grounded-answer prompt: "use only this evidence, cite [SOURCE_N], say
    when evidence is insufficient"
      v
    LLMProvider.generate(prompt)
      v
    Raw answer text (still contains [SOURCE_N] labels, not yet resolved)

Like EmbeddingProvider, calling code depends only on the LLMProvider
interface + create_llm_provider() factory — never a concrete provider class
directly — so swapping LLMs later needs no changes at call sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from providers import LLMProviderName

GROUNDED_ANSWER_PROMPT = """Answer the question using ONLY the evidence below.
Cite every claim with the matching label, using EXACTLY this format with
plain ASCII square brackets: [SOURCE_N] (for example [SOURCE_1]). Do not use
full-width brackets or any other bracket style. If the evidence does not
contain enough information to answer, say so explicitly instead of guessing.

Evidence:
{context}

Question: {question}

Answer:"""


class LLMProvider(ABC):
    """Anything that can generate text from a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the model's text completion for a prompt."""


def create_llm_provider(name: LLMProviderName) -> LLMProvider:
    """Factory: build the LLMProvider matching `name`."""
    if name == LLMProviderName.GROQ:
        from groq_llm_provider import GroqLLMProvider
        return GroqLLMProvider()
    raise NotImplementedError(f"No LLM provider wired up yet for {name}")


def build_grounded_prompt(question: str, context: str) -> str:
    """Fill the grounded-answer template with the question and evidence."""
    return GROUNDED_ANSWER_PROMPT.format(context=context, question=question)
