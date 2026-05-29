"""Provider interfaces and the shared raw types the ingestion layer converges on.

Both platforms and both Instagram providers implement these protocols, so the
pipeline branches only at extraction and is identical downstream (PRD FR-4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class TranscriptSegment:
    """A timed slice of speech. `start`/`end` are seconds from the video start."""

    text: str
    start: float
    end: float


@dataclass
class RawMetadata:
    """Platform-agnostic raw extraction result, before normalization."""

    source: str  # "youtube" | "instagram"
    url: str
    creator: str | None = None
    follower_count: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    hashtags: list[str] = field(default_factory=list)
    upload_date: date | None = None
    duration: float | None = None
    title: str | None = None
    caption: str | None = None
    # Set by IG providers when no transcript exists; consumed by transcribe step.
    media_url: str | None = None


class MetadataProvider(Protocol):
    """Extracts metadata for a single URL of one platform."""

    def fetch(self, url: str) -> RawMetadata: ...


class TranscriptProvider(Protocol):
    """Returns timed transcript segments for a single URL/media."""

    def fetch(self, raw: RawMetadata) -> list[TranscriptSegment]: ...
