"""Video metadata: the normalized, cross-platform schema and its ORM table.

`engagement_rate` is deliberately NOT a stored column. It is derived from
likes/comments/views in code (see `VideoMetadata.engagement_rate`) so it can
never drift from its inputs (PRD FR-5, NFR-1, data §9).
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, computed_field
from sqlalchemy import BigInteger, Date, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def compute_engagement_rate(
    likes: int | None, comments: int | None, views: int | None
) -> float | None:
    """(likes + comments) / views * 100 — the one number that must be exact."""
    if not views:  # None or 0 → undefined
        return None
    return round(((likes or 0) + (comments or 0)) / views * 100, 4)


class Video(Base):
    __tablename__ = "videos"

    # "A" (YouTube) or "B" (Instagram). Primary key — one pair per instance.
    video_id: Mapped[str] = mapped_column(String(1), primary_key=True)
    source: Mapped[str] = mapped_column(String(16))  # youtube | instagram
    url: Mapped[str] = mapped_column(String)

    creator: Mapped[str | None] = mapped_column(String, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    views: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    likes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comments: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    upload_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def engagement_rate(self) -> float | None:
        return compute_engagement_rate(self.likes, self.comments, self.views)


class VideoMetadata(BaseModel):
    """Normalized cross-platform schema produced by the ingestion layer and
    returned by the API. Engagement rate is a computed field."""

    video_id: str
    source: str
    url: str
    creator: str | None = None
    follower_count: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    hashtags: list[str] = []
    upload_date: date | None = None
    duration: float | None = None
    title: str | None = None
    caption: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def engagement_rate(self) -> float | None:
        return compute_engagement_rate(self.likes, self.comments, self.views)

    @classmethod
    def from_orm_video(cls, v: Video) -> "VideoMetadata":
        return cls(
            video_id=v.video_id,
            source=v.source,
            url=v.url,
            creator=v.creator,
            follower_count=v.follower_count,
            views=v.views,
            likes=v.likes,
            comments=v.comments,
            hashtags=list(v.hashtags or []),
            upload_date=v.upload_date,
            duration=v.duration,
            title=v.title,
            caption=v.caption,
        )
