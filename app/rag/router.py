"""Intent router — the decision the whole system is built around.

Classifies each question as quantitative, qualitative, or hybrid so it can be
sent down the right path. Quantitative questions must be computed, never
retrieved; qualitative ones are real retrieval; hybrid needs both (README).
"""
from __future__ import annotations

from typing import Literal, get_args

from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.llm import get_router_llm

Intent = Literal["quantitative", "qualitative", "hybrid"]
_INTENTS = get_args(Intent)

_SYSTEM = """You classify a user's question about a comparison of two short-form \
videos (A = YouTube, B = Instagram) into exactly one intent:

- "quantitative": answerable purely from numeric metadata (engagement rate, \
views, likes, comments, follower count, duration, upload date, creator name). \
These must be computed/looked up, never inferred.
- "qualitative": about the CONTENT — hooks, transcript, tone, what was said, \
suggestions for improvement. Needs retrieval over transcript text.
- "hybrid": needs BOTH a number and content reasoning (e.g. "why did A get more \
engagement than B?").

When in doubt, or if the question could plausibly need a number AND content, \
choose "hybrid" — it includes the metrics, so a borderline call never drops a \
number. Only choose "quantitative" or "qualitative" when the question clearly \
needs just one.

Use the chat history to resolve follow-ups. Reply with ONE word only — exactly \
one of: quantitative, qualitative, hybrid. No punctuation, no explanation."""


def classify(question: str, history: str = "") -> Intent:
    """Classify intent with a plain one-word completion.

    Deliberately avoids `.with_structured_output()` / tool-calling: OpenRouter
    may route the cheap model to a provider whose function-calling fails (e.g.
    Groq returning "Failed to call a function"). A parsed word is provider-
    agnostic. Falls back to "hybrid" — the safe superset that gathers both
    metrics and transcript evidence — if the reply is unrecognized.
    """
    user = question if not history else f"Chat history:\n{history}\n\nQuestion: {question}"
    reply = get_router_llm().invoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=user)]
    )
    text = (reply.content or "").strip().lower()
    for intent in _INTENTS:
        if intent in text:
            return intent  # type: ignore[return-value]
    return "hybrid"
