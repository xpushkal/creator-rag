"""Instagram metadata extraction.

This is the riskiest part of the system (README "The Instagram problem").
Providers sit behind the same `MetadataProvider` interface so production can
switch from instaloader to a managed scraper by env var, not a rewrite.

Instagram gives NO transcript — only metadata, caption, and a media URL. The
pipeline therefore downloads the media and runs Whisper on it (see
`_download_media`, intentionally explicit as the most fragile step).
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import httpx
import instaloader

from app.core.config import get_settings
from app.ingest.base import RawMetadata

_HASHTAG_RE = re.compile(r"#(\w+)")
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([\w-]+)")

# Reused download dir; gitignored. One file per shortcode so re-ingest is cheap.
_MEDIA_DIR = Path("data/media")


def _shortcode(url: str) -> str:
    m = _SHORTCODE_RE.search(url)
    if not m:
        raise ValueError(f"Could not parse Instagram shortcode from: {url}")
    return m.group(1)


class InstaloaderProvider:
    """Free, local, demo-grade. Rate-limits aggressively (429) and heavy use can
    get a logged-in account banned — demo only (README)."""

    def __init__(self) -> None:
        self._loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
        )
        # Optional logged-in session enables follower counts and eases limits.
        username = get_settings().ig_username
        if username:
            try:
                self._loader.load_session_from_file(username)
            except FileNotFoundError:
                pass  # best-effort; falls back to anonymous

    def fetch(self, url: str) -> RawMetadata:
        post = instaloader.Post.from_shortcode(
            self._loader.context, _shortcode(url)
        )
        caption = post.caption or ""
        hashtags = list(post.caption_hashtags) or _HASHTAG_RE.findall(caption)

        follower_count = None
        try:  # requires an authenticated session; best-effort (PRD §14)
            follower_count = post.owner_profile.followers
        except Exception:
            pass

        return RawMetadata(
            source="instagram",
            url=url,
            creator=post.owner_username,
            follower_count=follower_count,
            views=post.video_view_count,
            likes=post.likes,
            comments=post.comments,
            hashtags=hashtags,
            upload_date=post.date_utc.date() if post.date_utc else None,
            duration=getattr(post, "video_duration", None),
            title=None,
            caption=caption,
            media_url=post.video_url,
        )


def _download_media(media_url: str, shortcode: str) -> Path:
    """Download the Reel's media to a local file for transcription.

    THE MOST FRAGILE STEP. Instagram CDN URLs are signed and short-lived, and
    their markup changes. Test against a live Reel before relying on it.
    """
    _MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    dest = _MEDIA_DIR / f"{shortcode}.mp4"
    if dest.exists():  # cache: never re-download the same Reel
        return dest

    with httpx.stream("GET", media_url, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(
            dir=_MEDIA_DIR, suffix=".part", delete=False
        ) as tmp:
            for block in r.iter_bytes(chunk_size=1 << 16):
                tmp.write(block)
            tmp_path = Path(tmp.name)
    tmp_path.rename(dest)
    return dest


def download_reel_media(raw: RawMetadata) -> Path:
    """Public entry: download media for a normalized IG record."""
    if not raw.media_url:
        raise ValueError("Instagram metadata has no media_url to download")
    return _download_media(raw.media_url, _shortcode(raw.url))
