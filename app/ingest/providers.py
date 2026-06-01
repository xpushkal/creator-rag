"""Provider selection by config.

The Instagram metadata provider is chosen by `IG_PROVIDER` at runtime so the
production path (managed scraper) is a config flag, not a rewrite (README/NFR-5).
"""
from __future__ import annotations

import datetime as dt
import re

import httpx

from app.core.config import get_settings
from app.ingest.base import MetadataProvider, RawMetadata
from app.ingest.instagram import InstaloaderProvider

_HASHTAG_RE = re.compile(r"#(\w+)")


def _first(item: dict, *keys, default=None):
    """Return the first present, non-None value among keys (schemas vary)."""
    for k in keys:
        if item.get(k) is not None:
            return item[k]
    return default


class ApifyProvider:
    """Managed scraper path (~$1.50/1k posts), proxies + anti-automation —
    the production path that gets past Instagram's anti-bot (README).

    Runs an Apify Instagram-scraper actor synchronously for one Reel URL and
    normalizes the first dataset item into RawMetadata.
    """

    def fetch(self, url: str) -> RawMetadata:
        s = get_settings()
        if not s.apify_api_token:
            raise RuntimeError("APIFY_API_TOKEN is not set")

        endpoint = (
            f"https://api.apify.com/v2/acts/{s.apify_actor}"
            f"/run-sync-get-dataset-items?token={s.apify_api_token}"
        )
        payload = {
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": 1,
            "addParentData": False,
        }
        # Actor cold-starts can take tens of seconds; run-sync blocks until done.
        resp = httpx.post(endpoint, json=payload, timeout=180)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            raise RuntimeError(f"Apify returned no data for {url}")
        return self._normalize(items[0], url)

    @staticmethod
    def _normalize(item: dict, url: str) -> RawMetadata:
        caption = _first(item, "caption", default="") or ""
        hashtags = _first(item, "hashtags", default=None) or _HASHTAG_RE.findall(caption)

        upload_date = None
        ts = _first(item, "timestamp", "takenAtTimestamp")
        if isinstance(ts, str):
            try:
                upload_date = dt.datetime.fromisoformat(
                    ts.replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass

        return RawMetadata(
            source="instagram",
            url=url,
            creator=_first(item, "ownerUsername", "ownerFullName"),
            follower_count=_first(item, "ownerFollowersCount", "followersCount"),
            views=_first(item, "videoViewCount", "videoPlayCount", "playCount"),
            likes=_first(item, "likesCount", "likes"),
            comments=_first(item, "commentsCount", "comments"),
            hashtags=list(hashtags),
            upload_date=upload_date,
            duration=_first(item, "videoDuration"),
            title=None,
            caption=caption,
            media_url=_first(item, "videoUrl", "videoUrlBackup"),
        )


def get_instagram_provider() -> MetadataProvider:
    provider = get_settings().ig_provider.lower()
    if provider == "instaloader":
        return InstaloaderProvider()
    if provider == "apify":
        return ApifyProvider()
    raise ValueError(f"Unknown IG_PROVIDER: {provider!r}")
