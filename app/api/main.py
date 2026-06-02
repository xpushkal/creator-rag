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
from app.core.net import force_ipv4

# Prefer IPv4 for all outbound calls (yt-dlp, transcript API, LLM SDK) so a
# broken IPv6 route can't stall ingestion for ~75s. Must run before any
# network client is created.
force_ipv4()
from app.core.db import get_session, init_db
from app.ingest.pipeline import ingest_pair
from app.models.video import Video, VideoMetadata
from app.rag.graph import GRAPH


# Surface ingest timing logs (own handler so they show regardless of uvicorn's
# logging config, which doesn't attach a handler to the root logger).
_ingest_log = logging.getLogger("creator_rag")
_ingest_log.setLevel(logging.INFO)
if not _ingest_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    _ingest_log.addHandler(_h)
    _ingest_log.propagate = False


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


@app.post("/seed", response_model=VideosResponse)
def seed(session: Session = Depends(get_session)) -> VideosResponse:
    """Populate the two demo videos so a hosted instance isn't empty.

    Live YouTube/Instagram scraping fails from cloud IPs, so this loads the
    deterministic demo pair (transcripts embedded locally with BGE) straight
    into the DB. Idempotent: if videos already exist it returns them untouched,
    so it can only fill an empty database — never overwrite real ingests.
    """
    existing = session.query(Video).order_by(Video.video_id).all()
    if len(existing) < 2:
        # Imported lazily: pulls in the embedding model only when actually seeding.
        from app.ingest.pipeline import _persist
        from scripts.seed import A_META, A_SEGMENTS, B_META, B_SEGMENTS

        _persist(session, A_META, A_SEGMENTS)
        _persist(session, B_META, B_SEGMENTS)
        existing = session.query(Video).order_by(Video.video_id).all()
    return VideosResponse(videos=[VideoMetadata.from_orm_video(v) for v in existing])


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
