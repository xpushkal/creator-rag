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
from app.ingest.youtube import (
    YouTubeMetadataProvider,
    YouTubeTranscriptProvider,
    download_youtube_audio,
)
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
    # Metadata (yt-dlp) and the transcript (transcript API) both derive only
    # from the URL and hit different endpoints, so fetch them concurrently
    # instead of serially. The transcript provider only reads `raw.url`, so a
    # minimal RawMetadata is enough to start it before metadata returns.
    with _timed("youtube metadata + transcript (parallel)"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            meta_future = pool.submit(YouTubeMetadataProvider().fetch, url)
            trans_future = pool.submit(
                YouTubeTranscriptProvider().fetch,
                RawMetadata(source="youtube", url=url),
            )
            raw = meta_future.result()
            segments = trans_future.result()
    # YouTube increasingly blocks the transcript API. Fall back to the same
    # fast Groq Whisper path used for Instagram so there's always content.
    if not segments:
        logger.info("ingest: youtube transcript empty → audio + Whisper fallback")
        with _timed("youtube audio download"):
            audio_path = download_youtube_audio(url)
        with _timed("whisper transcription (youtube fallback)"):
            segments = transcribe(audio_path)
    return raw, segments


def _extract_instagram(url: str) -> tuple[RawMetadata, list[TranscriptSegment]]:
    with _timed("instagram metadata"):
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
    both videos concurrently. Persisting is pipelined with extraction: as soon
    as one video's extraction finishes it is persisted on the main thread while
    the other video is still extracting, so the CPU-bound embedding overlaps the
    other's network wait. DB writes stay on the single caller session (sessions
    aren't thread-safe), which the main thread alone touches.
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

    # Extract both videos in parallel (I/O-bound → threads help) and persist
    # each as it completes, on the main thread, while the other still extracts.
    if to_extract:
        with _timed("extract + persist (both videos)"):
            with ThreadPoolExecutor(max_workers=len(to_extract)) as pool:
                futures = {
                    pool.submit(extractor, url): video_id
                    for video_id, url, extractor in to_extract
                }
                for future in as_completed(futures):
                    video_id = futures[future]
                    raw, segments = future.result()
                    meta = normalize(raw, video_id)
                    with _timed(f"persist video {video_id}"):
                        _persist(session, meta, segments)
                    results[video_id] = meta

    return results
