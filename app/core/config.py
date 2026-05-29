"""Single source of truth for runtime configuration.

Everything external (LLM provider/models, Instagram provider, embedding model,
Whisper size) is set here from the environment, so swapping a provider is a
config change rather than a code change (PRD NFR-5).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = (
        "postgresql+psycopg://creator:creator@localhost:5432/creator_rag"
    )

    # LLM via OpenRouter (two tiers, swappable by model name)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    router_model: str = "meta-llama/llama-3.1-8b-instruct"
    synthesis_model: str = "anthropic/claude-3.5-sonnet"

    # Instagram metadata provider: "instaloader" | "apify"
    ig_provider: str = "instaloader"
    apify_api_token: str = ""
    ig_username: str = ""

    # Embeddings (local). bge-small-en-v1.5 → 384 dims.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Transcription (local faster-whisper)
    whisper_model: str = "base"

    # CORS (comma-separated)
    cors_origins: str = "http://localhost:3000"

    # Retrieval
    retrieval_top_k: int = 6

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
