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
    # quota for the full context window. Roomy enough not to truncate a
    # thorough comparison (the 1024 cap was only to dodge OpenRouter's credit
    # pre-check, which Groq doesn't do).
    synthesis_max_tokens: int = 3000

    # Instagram metadata provider: "instaloader" | "apify"
    ig_provider: str = "instaloader"
    apify_api_token: str = ""
    apify_actor: str = "apify~instagram-scraper"
    ig_username: str = ""

    # Embeddings (local). bge-small-en-v1.5 → 384 dims.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # YouTube increasingly blocks anonymous transcript/format access. Set to a
    # browser name (chrome|safari|firefox|edge|brave) to authenticate yt-dlp
    # with that browser's YouTube cookies. Empty = anonymous (may be blocked).
    yt_cookies_from_browser: str = ""

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
