"""The model layer — the one place provider/model choices live.

Two tiers through OpenRouter: a cheap, fast model for intent routing and a
flagship for synthesis. Swapping providers is changing the model name in config;
no other code changes (README, NFR-5).
"""
from __future__ import annotations

from functools import lru_cache

import httpx
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _http_clients() -> tuple[httpx.Client, httpx.AsyncClient]:
    """Sync + async HTTP clients that force IPv4.

    Binding the local address to 0.0.0.0 keeps the OpenAI SDK on IPv4. Without
    this, the first TCP connect tries an unreachable IPv6 route and blocks for
    the full ~75s connect timeout before falling back (curl avoids this via
    Happy Eyeballs). Reused across calls so the connection pool stays warm.
    """
    return (
        httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0")),
        httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0")),
    )


def _make(
    model: str, *, temperature: float, streaming: bool, max_tokens: int | None = None
) -> ChatOpenAI:
    s = get_settings()
    sync_client, async_client = _http_clients()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=streaming,
        max_tokens=max_tokens,
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        http_client=sync_client,
        http_async_client=async_client,
    )


@lru_cache(maxsize=1)
def get_router_llm() -> ChatOpenAI:
    """Cheap model for intent classification. Deterministic, one-word output.

    Tight max_tokens: the reply is a single word, and an uncapped default makes
    OpenRouter pre-reserve credit for the model's full output window.
    """
    return _make(
        get_settings().router_model, temperature=0.0, streaming=False, max_tokens=16
    )


@lru_cache(maxsize=1)
def get_synthesis_llm() -> ChatOpenAI:
    """Flagship model for the streamed, cited final answer.

    Cap output tokens: keeps answers tight and bounds per-query cost. Without a
    cap, OpenRouter pre-reserves credit for the model's full context (~65k),
    which can 402 on low-balance accounts before generating anything.
    """
    return _make(
        get_settings().synthesis_model,
        temperature=0.3,
        streaming=True,
        max_tokens=get_settings().synthesis_max_tokens,
    )
