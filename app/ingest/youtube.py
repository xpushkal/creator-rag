"""YouTube extraction: yt-dlp for metadata, youtube-transcript-api for the
transcript. The free path — no Whisper required.

Caveat (README): the transcript API is blocked from known cloud-provider IPs.
Works locally; a deployed instance needs a proxy on this call.
"""
from __future__ import annotations

import datetime as dt
import glob
import logging
import re
import time
from pathlib import Path
from typing import Callable, TypeVar

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from app.core.config import get_settings
from app.ingest.base import RawMetadata, TranscriptSegment

logger = logging.getLogger("creator_rag.ingest")

# Downloaded audio for the Whisper fallback; gitignored, cached per video id.
_AUDIO_DIR = Path("data/media")

# Substrings (lower-cased) that mark a transient TLS/connection drop worth
# retrying. YouTube intermittently resets the connection to its innertube API
# ("[SSL: UNEXPECTED_EOF_WHILE_READING] ... Unable to download API page"),
# which fails the whole ingest. We do NOT retry permanent failures like
# "video unavailable" / "private video" — those don't match these markers.
_TRANSIENT_MARKERS = (
    "ssl",
    "eof",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
    "unable to download",
    "remote end closed",
    "temporary failure",
    "max retries",
)

_T = TypeVar("_T")


def _is_transient(err: Exception) -> bool:
    msg = str(err).lower()
    return any(m in msg for m in _TRANSIENT_MARKERS)


def _with_retries(
    fn: Callable[[], _T], *, attempts: int = 3, base_delay: float = 1.0
) -> _T:
    """Run a YouTube network call, retrying transient TLS/connection drops with
    exponential backoff. yt-dlp's own retries don't reliably catch the SSL EOF
    YouTube throws at the innertube API, so we retry at the application level.
    Permanent failures (no captions, private video) aren't transient and raise
    immediately on the first attempt.
    """
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — re-raised below if not transient
            if not _is_transient(e) or i == attempts - 1:
                raise
            delay = base_delay * (2**i)
            logger.warning(
                "youtube: transient error (attempt %d/%d), retrying in %.0fs: %s",
                i + 1,
                attempts,
                delay,
                e,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # loop either returns or raises


def _ydl_opts(**extra) -> dict:
    """Base yt-dlp options, optionally authenticated with browser cookies to
    get past YouTube's anti-bot blocking (set YT_COOKIES_FROM_BROWSER)."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        # Bound each connection and let yt-dlp itself retry transient network
        # failures before our application-level _with_retries kicks in.
        "socket_timeout": 30,
        "retries": 5,
        "extractor_retries": 5,
        "fragment_retries": 5,
        **extra,
    }
    browser = get_settings().yt_cookies_from_browser.strip()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    return opts

_HASHTAG_RE = re.compile(r"#(\w+)")


def _parse_upload_date(raw: str | None) -> dt.date | None:
    if not raw:
        return None
    try:
        return dt.datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None


class YouTubeMetadataProvider:
    """Fetch metadata via yt-dlp without downloading the video."""

    def fetch(self, url: str) -> RawMetadata:
        # We only need metadata (the transcript comes from the transcript API,
        # not a download). Don't let format selection abort extraction:
        # ignore_no_formats_error keeps videos whose formats yt-dlp can't
        # resolve ("Requested format is not available") from failing ingest.
        opts = _ydl_opts(
            skip_download=True, ignore_no_formats_error=True, format=None
        )

        def _extract() -> dict:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = _with_retries(_extract)

        description = info.get("description") or ""
        hashtags = info.get("tags") or _HASHTAG_RE.findall(description)

        return RawMetadata(
            source="youtube",
            url=url,
            creator=info.get("uploader") or info.get("channel"),
            follower_count=info.get("channel_follower_count"),
            views=info.get("view_count"),
            likes=info.get("like_count"),
            comments=info.get("comment_count"),
            hashtags=list(hashtags),
            upload_date=_parse_upload_date(info.get("upload_date")),
            duration=info.get("duration"),
            title=info.get("title"),
            caption=description,
        )


class YouTubeTranscriptProvider:
    """Fetch the native transcript; returns [] if none is available."""

    @staticmethod
    def _video_id(url: str) -> str:
        m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
        if not m:
            raise ValueError(f"Could not parse YouTube video id from: {url}")
        return m.group(1)

    def fetch(self, raw: RawMetadata) -> list[TranscriptSegment]:
        vid = self._video_id(raw.url)
        try:
            # Retry transient TLS drops so a blip doesn't needlessly fall through
            # to the slow audio+Whisper path; permanent "no captions" raises
            # immediately and is caught below.
            entries = _with_retries(lambda: YouTubeTranscriptApi.get_transcript(vid))
        except Exception:
            # No captions / disabled / blocked → caller handles empty transcript.
            return []
        return [
            TranscriptSegment(
                text=e["text"].strip(),
                start=float(e["start"]),
                end=float(e["start"]) + float(e.get("duration", 0.0)),
            )
            for e in entries
            if e.get("text", "").strip()
        ]


def download_youtube_audio(url: str) -> Path:
    """Download the audio track for the Whisper fallback (used when the
    transcript API returns nothing — increasingly common as YouTube blocks it).

    bestaudio with no post-processing avoids an ffmpeg dependency; the file is
    cached per video id so re-ingest is free.
    """
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    vid = YouTubeTranscriptProvider._video_id(url)
    existing = glob.glob(str(_AUDIO_DIR / f"yt_{vid}.*"))
    if existing:
        return Path(existing[0])

    out_tmpl = str(_AUDIO_DIR / f"yt_{vid}.%(ext)s")
    opts = _ydl_opts(format="bestaudio/best", outtmpl=out_tmpl)

    def _download() -> None:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    _with_retries(_download)
    files = glob.glob(str(_AUDIO_DIR / f"yt_{vid}.*"))
    if not files:
        raise RuntimeError(f"Failed to download audio for {url}")
    return Path(files[0])
