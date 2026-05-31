"""FastAPI surface: ingest a pair, fetch the two cards, and stream chat.

Chat streams token-by-token over SSE through the LangGraph agent (FR-11), and
emits the routed intent and source citations as structured events (FR-12).
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChatRequest,
    IngestRequest,
    IngestResponse,
    VideosResponse,
)
from app.core.config import get_settings
from app.core.db import get_session, init_db
from app.ingest.pipeline import ingest_pair
from app.models.video import Video, VideoMetadata
from app.rag.graph import GRAPH


# Surface ingest timing logs even when uvicorn runs at a quieter level.
logging.getLogger("creator_rag").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # enable pgvector + create tables/index (idempotent)
    yield


app = FastAPI(title="creator-rag", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, session: Session = Depends(get_session)) -> IngestResponse:
    try:
        videos = ingest_pair(
            session, req.youtube_url, req.instagram_url, force=req.force
        )
    except Exception as e:  # extraction is the fragile part — surface clearly
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {e}") from e
    return IngestResponse(videos=videos)


@app.get("/videos", response_model=VideosResponse)
def videos(session: Session = Depends(get_session)) -> VideosResponse:
    rows = session.query(Video).order_by(Video.video_id).all()
    return VideosResponse(videos=[VideoMetadata.from_orm_video(v) for v in rows])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def _chat_stream(message: str, thread_id: str) -> AsyncIterator[str]:
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=message)], "question": message}

    try:
        async for mode, chunk in GRAPH.astream(
            inputs, config=config, stream_mode=["updates", "messages"]
        ):
            if mode == "updates":
                for node, update in chunk.items():
                    if node == "route" and update.get("intent"):
                        yield _sse({"type": "intent", "intent": update["intent"]})
                    if update and update.get("citations"):
                        yield _sse(
                            {"type": "citations", "citations": update["citations"]}
                        )
            elif mode == "messages":
                msg, meta = chunk
                # Only stream tokens from the synthesis node.
                if meta.get("langgraph_node") == "synthesize" and msg.content:
                    yield _sse({"type": "token", "content": msg.content})
    except Exception as e:
        # Surface failures as a visible event rather than a silently dropped
        # stream (e.g. a bad model slug returns 404 mid-synthesis).
        yield _sse({"type": "error", "message": _friendly_error(e)})

    yield _sse({"type": "done"})


def _friendly_error(e: Exception) -> str:
    """Map noisy provider exceptions to a short, human message."""
    text = str(e)
    if "402" in text or "more credits" in text:
        return (
            "The LLM provider is out of credits. Top up your OpenRouter balance "
            "or switch the model provider (see SYNTHESIS_MODEL in .env)."
        )
    if "404" in text and "endpoints" in text:
        return "The configured model isn't available on the provider. Check SYNTHESIS_MODEL."
    if "rate limit" in text.lower() or "429" in text:
        return "The LLM provider is rate-limiting requests. Try again in a moment."
    # Fall back to the exception's own first line.
    return text.split("\n", 1)[0][:300]


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _chat_stream(req.message, req.thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
