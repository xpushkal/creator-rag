"""Qualitative path: pgvector similarity search over transcript chunks.

Returns chunks with their ids so the synthesizer can cite which video and which
chunk a content claim came from (FR-12).

This is a *comparison* product, so retrieval is deliberately not a plain global
top-k: a naive nearest-k often returns chunks from only one video (one video's
phrasing simply sits closer to the query), leaving the LLM with nothing to
compare against. We over-fetch once, then balance the result across both videos
so each side is always represented, and we surface the purpose-built hook chunk
when the question is about the opening (UC-3).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.embeddings.embedder import embed_query
from app.models.chunk import MODALITY_HOOK, Chunk

# Candidate multiplier: pull this many * top_k before balancing, so each video
# has enough near neighbours to draw a fair share from.
_CANDIDATE_FACTOR = 4

# Question is about the opening/hook → make sure the hook chunks are included.
_HOOK_QUERY_RE = re.compile(
    r"\b(hook|hooks|first \d+ ?s(econds?)?|opening|intro|beginning|start)\b",
    re.IGNORECASE,
)


@dataclass
class RetrievedChunk:
    chunk_id: int
    video_id: str
    modality: str
    text: str
    start: float | None
    end: float | None
    distance: float


def _balance_by_video(rows: list, k: int) -> list:
    """Pick up to k rows, guaranteeing every video is represented.

    `rows` are (Chunk, distance) tuples already sorted by ascending distance.
    We round-robin across videos taking each one's nearest remaining chunk, so a
    single video can't monopolise the budget while a closer chunk still beats a
    farther one within each video. Pure (no DB) so it's unit-testable.
    """
    by_vid: dict[str, list] = defaultdict(list)
    for row in rows:  # input is distance-sorted, so per-video lists stay sorted
        by_vid[row[0].video_id].append(row)

    # Video order = order of first (nearest) appearance, so the closest match's
    # video gets first pick on each round.
    vids = list(by_vid.keys())
    idx = {v: 0 for v in vids}
    picked: list = []
    while len(picked) < k and any(idx[v] < len(by_vid[v]) for v in vids):
        for v in vids:
            if idx[v] < len(by_vid[v]):
                picked.append(by_vid[v][idx[v]])
                idx[v] += 1
                if len(picked) >= k:
                    break

    picked.sort(key=lambda r: r[1])  # final ordering by distance for the prompt
    return picked


def retrieve(session: Session, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Cosine-distance search, balanced across both videos and hook-aware."""
    k = top_k or get_settings().retrieval_top_k
    qvec = embed_query(question)

    distance = Chunk.embedding.cosine_distance(qvec).label("distance")
    candidates = session.execute(
        select(Chunk, distance).order_by(distance).limit(k * _CANDIDATE_FACTOR)
    ).all()

    selected = _balance_by_video(candidates, k)

    # Opening/hook questions: ensure each video's hook chunk is present even if
    # it didn't win on raw cosine distance — it's the chunk built for exactly
    # this question (chunker.py). De-dup against what balancing already picked.
    if _HOOK_QUERY_RE.search(question):
        chosen_ids = {row[0].chunk_id for row in selected}
        for row in candidates:
            chunk, _dist = row
            if chunk.modality == MODALITY_HOOK and chunk.chunk_id not in chosen_ids:
                selected.append(row)
                chosen_ids.add(chunk.chunk_id)

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
        for c, dist in selected
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
