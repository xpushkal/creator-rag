"""Provider selection by config.

The Instagram metadata provider is chosen by `IG_PROVIDER` at runtime so the
production path (managed scraper) is a config flag, not a rewrite (README/NFR-5).
"""
from __future__ import annotations

from app.core.config import get_settings
from app.ingest.base import MetadataProvider, RawMetadata
from app.ingest.instagram import InstaloaderProvider


class ApifyProvider:
    """Managed scraper path (~$1.50/1k posts), proxies + anti-automation.

    Stub: implements the same interface so it can be wired in Phase 2 without
    touching the pipeline. Requires APIFY_API_TOKEN.
    """

    def fetch(self, url: str) -> RawMetadata:  # pragma: no cover - not wired yet
        raise NotImplementedError(
            "Apify provider not implemented in this build. "
            "Set IG_PROVIDER=instaloader."
        )


def get_instagram_provider() -> MetadataProvider:
    provider = get_settings().ig_provider.lower()
    if provider == "instaloader":
        return InstaloaderProvider()
    if provider == "apify":
        return ApifyProvider()
    raise ValueError(f"Unknown IG_PROVIDER: {provider!r}")
