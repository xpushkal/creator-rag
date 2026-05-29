"""API request/response models."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.video import VideoMetadata


class IngestRequest(BaseModel):
    youtube_url: str
    instagram_url: str
    force: bool = False  # re-ingest even if cached


class IngestResponse(BaseModel):
    videos: dict[str, VideoMetadata]  # keyed by video_id ("A"/"B")


class VideosResponse(BaseModel):
    videos: list[VideoMetadata]


class ChatRequest(BaseModel):
    message: str
    thread_id: str  # conversation id for cross-turn memory
