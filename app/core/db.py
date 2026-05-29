"""Database engine, session factory, and schema bootstrap.

Both the structured metadata (source of truth for number questions) and the
transcript vector chunks live in this one Postgres instance via pgvector, so a
video's row and its chunks stay transactionally consistent (README rationale).
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Enable pgvector and create all tables. Safe to call repeatedly."""
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # HNSW index for fast similarity search on the chunk embeddings.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
                "ON chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )
