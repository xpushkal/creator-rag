"""Intent router — the decision the whole system is built around.

Classifies each question as quantitative, qualitative, or hybrid so it can be
sent down the right path. Quantitative questions must be computed, never
retrieved; qualitative ones are real retrieval; hybrid needs both (README).
"""
from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.rag.llm import get_router_llm

Intent = Literal["quantitative", "qualitative", "hybrid"]

_SYSTEM = """You classify a user's question about a comparison of two short-form \
videos (A = YouTube, B = Instagram) into exactly one intent:

- "quantitative": answerable purely from numeric metadata (engagement rate, \
views, likes, comments, follower count, duration, upload date, creator name). \
These must be computed/looked up, never inferred.
- "qualitative": about the CONTENT — hooks, transcript, tone, what was said, \
suggestions for improvement. Needs retrieval over transcript text.
- "hybrid": needs BOTH a number and content reasoning (e.g. "why did A get more \
engagement than B?").

Use the chat history to resolve follow-ups. Respond with the intent only."""


class _Classification(BaseModel):
    intent: Intent = Field(description="One of quantitative, qualitative, hybrid")


def classify(question: str, history: str = "") -> Intent:
    llm = get_router_llm().with_structured_output(_Classification)
    user = question if not history else f"Chat history:\n{history}\n\nQuestion: {question}"
    result: _Classification = llm.invoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=user)]
    )
    return result.intent
