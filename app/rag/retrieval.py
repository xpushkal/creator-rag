"""Qualitative path: pgvector similarity search over transcript chunks.

Returns chunks with their ids so the synthesizer can cite which video and which
chunk a content claim came from (FR-12).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.embeddings.embedder import embed_query
from app.models.chunk import Chunk


@dataclass
class RetrievedChunk:
    chunk_id: int
    video_id: str
    modality: str
    text: str
    start: float | None
    end: float | None
    distance: float


def retrieve(session: Session, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Cosine-distance search across both videos' chunks for the query."""
    k = top_k or get_settings().retrieval_top_k
    qvec = embed_query(question)

    distance = Chunk.embedding.cosine_distance(qvec).label("distance")
    rows = session.execute(
        select(Chunk, distance).order_by(distance).limit(k)
    ).all()

    return [
        RetrievedChunk(
            chunk_id=c.chunk_id,
            video_id=c.video_id,
            modality=c.modality,
            text=c.text,
            start=c.start,
            end=c.end,
            distance=float(dist),
        )
        for c, dist in rows
    ]


def build_chunk_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a citable context block."""
    if not chunks:
        return "No transcript content was retrieved."
    lines = ["TRANSCRIPT EVIDENCE (cite by [Video X, chunk N]):"]
    for c in chunks:
        ts = ""
        if c.start is not None:
            ts = f" @{c.start:.0f}-{c.end:.0f}s" if c.end is not None else f" @{c.start:.0f}s"
        lines.append(
            f"[Video {c.video_id}, chunk {c.chunk_id}, {c.modality}{ts}] {c.text}"
        )
    return "\n".join(lines)
