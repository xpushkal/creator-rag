"""The LangGraph agent: router -> {quant | qual | hybrid} -> synthesize.

A router is a graph with branches and a merge, not a linear chain (README). The
checkpointer gives cross-turn memory for free: messages persist per thread_id so
follow-ups resolve against prior context (FR-13).

State is kept serializable (no DB session in it); nodes open their own session.
Citations gathered by the retrieval nodes are surfaced via final graph state.
"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.core.db import SessionLocal
from app.rag.llm import get_synthesis_llm
from app.rag.quant import build_metrics_context
from app.rag.retrieval import build_chunk_context, retrieve
from app.rag.router import classify
from app.rag.synthesize import build_system_prompt


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    intent: str
    context: str
    citations: list[dict]


def _history_text(messages: list[BaseMessage], limit: int = 6) -> str:
    recent = messages[-limit:]
    out = []
    for m in recent:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        out.append(f"{role}: {m.content}")
    return "\n".join(out)


def _route(state: ChatState) -> dict:
    history = _history_text(state["messages"][:-1])  # exclude current question
    intent = classify(state["question"], history)
    return {"intent": intent}


def _quant(state: ChatState) -> dict:
    with SessionLocal() as session:
        return {"context": build_metrics_context(session), "citations": []}


def _qual(state: ChatState) -> dict:
    with SessionLocal() as session:
        chunks = retrieve(session, state["question"])
        citations = [
            {
                "video_id": c.video_id,
                "chunk_id": c.chunk_id,
                "modality": c.modality,
                "start": c.start,
                "end": c.end,
            }
            for c in chunks
        ]
        return {"context": build_chunk_context(chunks), "citations": citations}


def _hybrid(state: ChatState) -> dict:
    with SessionLocal() as session:
        metrics = build_metrics_context(session)
        chunks = retrieve(session, state["question"])
        citations = [
            {
                "video_id": c.video_id,
                "chunk_id": c.chunk_id,
                "modality": c.modality,
                "start": c.start,
                "end": c.end,
            }
            for c in chunks
        ]
        context = f"{metrics}\n\n{build_chunk_context(chunks)}"
        return {"context": context, "citations": citations}


def _synthesize(state: ChatState) -> dict:
    system = build_system_prompt(state["context"])
    # Full conversation (memory) + the system context for this turn.
    messages = [system, *state["messages"]]
    response = get_synthesis_llm().invoke(messages)
    return {"messages": [response]}


def _branch(state: ChatState) -> str:
    return state["intent"]


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("route", _route)
    g.add_node("quantitative", _quant)
    g.add_node("qualitative", _qual)
    g.add_node("hybrid", _hybrid)
    g.add_node("synthesize", _synthesize)

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        _branch,
        {
            "quantitative": "quantitative",
            "qualitative": "qualitative",
            "hybrid": "hybrid",
        },
    )
    for node in ("quantitative", "qualitative", "hybrid"):
        g.add_edge(node, "synthesize")
    g.add_edge("synthesize", END)

    return g.compile(checkpointer=MemorySaver())


# Single compiled graph instance (the MemorySaver holds per-thread memory).
GRAPH = build_graph()
