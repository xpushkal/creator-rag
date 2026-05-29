"""Map platform-agnostic raw extraction into the normalized VideoMetadata.

Convergence point of the branched pipeline (PRD FR-4). YouTube → video_id "A",
Instagram → video_id "B".
"""
from __future__ import annotations

from app.ingest.base import RawMetadata
from app.models.video import VideoMetadata


def normalize(raw: RawMetadata, video_id: str) -> VideoMetadata:
    return VideoMetadata(
        video_id=video_id,
        source=raw.source,
        url=raw.url,
        creator=raw.creator,
        follower_count=raw.follower_count,
        views=raw.views,
        likes=raw.likes,
        comments=raw.comments,
        hashtags=raw.hashtags,
        upload_date=raw.upload_date,
        duration=raw.duration,
        title=raw.title,
        caption=raw.caption,
    )
