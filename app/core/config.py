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

    # LLM via any OpenAI-compatible provider (Groq, OpenRouter, DeepSeek,
    # Gemini OpenAI-compat, local Ollama...). Swap by changing base_url + key
    # + model names — no code change (NFR-5).
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    router_model: str = "llama-3.3-70b-versatile"
    synthesis_model: str = "llama-3.3-70b-versatile"
    # Cap synthesis output: bounds cost and avoids providers pre-reserving
    # credit/quota for the model's full context window.
    synthesis_max_tokens: int = 1024

    # Instagram metadata provider: "instaloader" | "apify"
    ig_provider: str = "instaloader"
    apify_api_token: str = ""
    ig_username: str = ""

    # Embeddings (local). bge-small-en-v1.5 → 384 dims.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Transcription provider: "groq" (hosted, fast) | "local" (faster-whisper)
    transcribe_provider: str = "groq"
    # Groq hosted Whisper (uses the LLM Groq key/base by default).
    groq_whisper_model: str = "whisper-large-v3-turbo"
    # Local faster-whisper model (used only when transcribe_provider="local").
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
