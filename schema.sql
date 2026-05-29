-- Reproducible schema mirroring the SQLAlchemy ORM (app/models/*).
-- Applied automatically by app.core.db.init_db() on startup; kept here for
-- manual setup / inspection. bge-small-en-v1.5 → 384-dim vectors.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS videos (
    video_id       VARCHAR(1) PRIMARY KEY,        -- 'A' (YouTube) | 'B' (Instagram)
    source         VARCHAR(16) NOT NULL,
    url            TEXT NOT NULL,
    creator        TEXT,
    follower_count BIGINT,
    views          BIGINT,
    likes          BIGINT,
    comments       BIGINT,
    hashtags       TEXT[] DEFAULT '{}',
    upload_date    DATE,
    duration       DOUBLE PRECISION,             -- seconds
    title          TEXT,
    caption        TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
    -- engagement_rate is derived in code, never stored (FR-5, NFR-1).
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id  SERIAL PRIMARY KEY,
    video_id  VARCHAR(1) NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    modality  VARCHAR(16) NOT NULL DEFAULT 'transcript',  -- transcript | hook | ocr | visual
    text      TEXT NOT NULL,
    start     DOUBLE PRECISION,
    "end"     DOUBLE PRECISION,
    embedding vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_video_id_idx ON chunks (video_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);
