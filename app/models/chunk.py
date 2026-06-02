"""Transcript chunks with their embeddings, tagged by video and modality.

Only content (transcript/hook) lives here. Numbers never become chunks — they
are answered from the `videos` table by the quantitative path, so the retriever
can never surface a number-as-text and have it treated as a fact (README).
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base

_EMBED_DIM = get_settings().embedding_dim

# Chunk modalities. transcript/hook are wired now; ocr/visual are reserved for
# the Phase-3 multimodal hook analysis (schema is additive).
MODALITY_TRANSCRIPT = "transcript"
MODALITY_HOOK = "hook"


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(
        String(1), ForeignKey("videos.video_id", ondelete="CASCADE"), index=True
    )
    modality: Mapped[str] = mapped_column(String(16), default=MODALITY_TRANSCRIPT)
    text: Mapped[str] = mapped_column(Text)
    start: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    end: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBED_DIM))
