"""End-to-end ingestion of a YouTube + Instagram pair.

Per video: extract → normalize → persist metadata → transcript → chunk → embed
→ persist chunks. Branches by source (YouTube has a free transcript; Instagram
needs download + Whisper) and converges to one schema. Idempotent per video:
re-ingesting a URL already stored is skipped, so re-comparisons are free
(README cost model).
"""
from __future__ import annotations

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

YOUTUBE_VIDEO_ID = "A"
INSTAGRAM_VIDEO_ID = "B"


def _extract_youtube(url: str) -> tuple[RawMetadata, list[TranscriptSegment]]:
    raw = YouTubeMetadataProvider().fetch(url)
    segments = YouTubeTranscriptProvider().fetch(raw)
    return raw, segments


def _extract_instagram(url: str) -> tuple[RawMetadata, list[TranscriptSegment]]:
    raw = get_instagram_provider().fetch(url)
    # Instagram gives no transcript: download media and run Whisper.
    segments: list[TranscriptSegment] = []
    if raw.media_url:
        media_path = download_reel_media(raw)
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


def _ingest_one(
    session: Session,
    *,
    url: str,
    video_id: str,
    extractor,
    force: bool,
) -> VideoMetadata:
    existing = session.get(Video, video_id)
    if existing and existing.url == url and not force:
        # Cache hit: same slot, same URL → skip re-ingest (README).
        return VideoMetadata.from_orm_video(existing)

    raw, segments = extractor(url)
    meta = normalize(raw, video_id)
    _persist(session, meta, segments)
    return meta


def ingest_pair(
    session: Session,
    youtube_url: str,
    instagram_url: str,
    *,
    force: bool = False,
) -> dict[str, VideoMetadata]:
    """Ingest both videos and return their normalized metadata keyed by slot."""
    a = _ingest_one(
        session,
        url=youtube_url,
        video_id=YOUTUBE_VIDEO_ID,
        extractor=_extract_youtube,
        force=force,
    )
    b = _ingest_one(
        session,
        url=instagram_url,
        video_id=INSTAGRAM_VIDEO_ID,
        extractor=_extract_instagram,
        force=force,
    )
    return {a.video_id: a, b.video_id: b}
