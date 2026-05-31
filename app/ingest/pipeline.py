"""End-to-end ingestion of a YouTube + Instagram pair.

Per video: extract → normalize → persist metadata → transcript → chunk → embed
→ persist chunks. Branches by source (YouTube has a free transcript; Instagram
needs download + Whisper) and converges to one schema. Idempotent per video:
re-ingesting a URL already stored is skipped, so re-comparisons are free
(README cost model).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.chunking.chunker import chunk_transcript
from app.embeddings.embedder import embed_passages
from app.ingest.base import RawMetadata, TranscriptSegment
from app.ingest.instagram import download_reel_media
from app.ingest.normalize import normalize
from app.ingest.providers import get_instagram_provider
from app.ingest.transcribe import transcribe
from app.ingest.youtube import YouTubeMetadataProvider, YouTubeTranscriptProvider
from app.models.chunk import Chunk
from app.models.video import Video, VideoMetadata

logger = logging.getLogger("creator_rag.ingest")

YOUTUBE_VIDEO_ID = "A"
INSTAGRAM_VIDEO_ID = "B"


@contextmanager
def _timed(label: str):
    """Log how long a pipeline step takes (visible in the server log)."""
    start = time.perf_counter()
    yield
    logger.info("ingest: %s took %.2fs", label, time.perf_counter() - start)


def _extract_youtube(url: str) -> tuple[RawMetadata, list[TranscriptSegment]]:
    with _timed("youtube metadata (yt-dlp)"):
        raw = YouTubeMetadataProvider().fetch(url)
    with _timed("youtube transcript (api)"):
        segments = YouTubeTranscriptProvider().fetch(raw)
    return raw, segments


def _extract_instagram(url: str) -> tuple[RawMetadata, list[TranscriptSegment]]:
    with _timed("instagram metadata (instaloader)"):
        raw = get_instagram_provider().fetch(url)
    # Instagram gives no transcript: download media and run Whisper.
    segments: list[TranscriptSegment] = []
    if raw.media_url:
        with _timed("instagram media download"):
            media_path = download_reel_media(raw)
        with _timed("whisper transcription"):
            segments = transcribe(media_path)
    return raw, segments


def _persist(
    session: Session,
    meta: VideoMetadata,
    segments: list[TranscriptSegment],
) -> None:
    video = Video(
        video_id=meta.video_id,
        source=meta.source,
        url=meta.url,
        creator=meta.creator,
        follower_count=meta.follower_count,
        views=meta.views,
        likes=meta.likes,
        comments=meta.comments,
        hashtags=meta.hashtags,
        upload_date=meta.upload_date,
        duration=meta.duration,
        title=meta.title,
        caption=meta.caption,
    )
    session.merge(video)  # upsert by primary key (video_id)
    # Persist the video row within the transaction before inserting chunks, so
    # the chunks' FK to video_id is satisfied (session has autoflush disabled).
    session.flush()

    # Replace any existing chunks for this video, then re-create.
    session.query(Chunk).filter(Chunk.video_id == meta.video_id).delete()

    chunks = chunk_transcript(segments)
    if chunks:
        with _timed(f"chunk+embed ({len(chunks)} chunks, BGE)"):
            embeddings = embed_passages([c.text for c in chunks])
        for c, vec in zip(chunks, embeddings):
            session.add(
                Chunk(
                    video_id=meta.video_id,
                    modality=c.modality,
                    text=c.text,
                    start=c.start,
                    end=c.end,
                    embedding=vec,
                )
            )
    session.commit()


def ingest_pair(
    session: Session,
    youtube_url: str,
    instagram_url: str,
    *,
    force: bool = False,
) -> dict[str, VideoMetadata]:
    """Ingest both videos and return their normalized metadata keyed by slot.

    Extraction (network + transcription — the slow, I/O-bound part) runs for
    both videos concurrently. DB writes stay on the single caller session and
    happen sequentially, since SQLAlchemy sessions aren't thread-safe.
    """
    jobs = [
        (YOUTUBE_VIDEO_ID, youtube_url, _extract_youtube),
        (INSTAGRAM_VIDEO_ID, instagram_url, _extract_instagram),
    ]

    results: dict[str, VideoMetadata] = {}
    to_extract: list[tuple[str, str, object]] = []
    for video_id, url, extractor in jobs:
        existing = session.get(Video, video_id)
        if existing and existing.url == url and not force:
            # Cache hit: same slot, same URL → skip re-ingest (README).
            results[video_id] = VideoMetadata.from_orm_video(existing)
        else:
            to_extract.append((video_id, url, extractor))

    # Phase 1: extract both videos in parallel (I/O-bound → threads help).
    extracted: dict[str, tuple[RawMetadata, list[TranscriptSegment]]] = {}
    if to_extract:
        with _timed("parallel extraction (both videos)"):
            with ThreadPoolExecutor(max_workers=len(to_extract)) as pool:
                futures = {
                    pool.submit(extractor, url): video_id
                    for video_id, url, extractor in to_extract
                }
                for future in as_completed(futures):
                    extracted[futures[future]] = future.result()

    # Phase 2: persist sequentially on the single session.
    for video_id, _url, _extractor in to_extract:
        raw, segments = extracted[video_id]
        meta = normalize(raw, video_id)
        with _timed(f"persist video {video_id}"):
            _persist(session, meta, segments)
        results[video_id] = meta

    return results
