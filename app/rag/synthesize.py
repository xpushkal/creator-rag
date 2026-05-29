"""Synthesis prompt construction for the streamed, cited final answer.

The synthesizer turns authoritative metrics and/or retrieved transcript evidence
into prose. It must never invent numbers (those come pre-computed) and must cite
content claims back to a specific video and chunk (FR-12).
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage

_SYSTEM = """You are an analyst comparing two short-form videos: Video A (YouTube) \
and Video B (Instagram Reel).

Rules:
- The METRICS block, when present, is authoritative and already computed. Quote \
those numbers exactly; never recalculate or invent a number.
- For any claim about video content (hooks, tone, what was said), cite the \
evidence inline as [Video X, chunk N] using the TRANSCRIPT EVIDENCE provided.
- If the evidence does not support a claim, say so rather than guessing.
- Be concise, concrete, and useful to a creator deciding what to do next.
"""


def build_system_prompt(context: str) -> SystemMessage:
    return SystemMessage(content=f"{_SYSTEM}\n\nCONTEXT:\n{context}")
