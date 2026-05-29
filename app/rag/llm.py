"""The model layer — the one place provider/model choices live.

Two tiers through OpenRouter: a cheap, fast model for intent routing and a
flagship for synthesis. Swapping providers is changing the model name in config;
no other code changes (README, NFR-5).
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def _make(model: str, *, temperature: float, streaming: bool) -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=streaming,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
    )


@lru_cache(maxsize=1)
def get_router_llm() -> ChatOpenAI:
    """Cheap model for structured intent classification. Deterministic."""
    return _make(get_settings().router_model, temperature=0.0, streaming=False)


@lru_cache(maxsize=1)
def get_synthesis_llm() -> ChatOpenAI:
    """Flagship model for the streamed, cited final answer."""
    return _make(get_settings().synthesis_model, temperature=0.3, streaming=True)
