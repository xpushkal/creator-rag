"""YouTube extraction: yt-dlp for metadata, youtube-transcript-api for the
transcript. The free path — no Whisper required.

Caveat (README): the transcript API is blocked from known cloud-provider IPs.
Works locally; a deployed instance needs a proxy on this call.
"""
from __future__ import annotations

import datetime as dt
import re

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from app.ingest.base import RawMetadata, TranscriptSegment

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
        opts = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "ignore_no_formats_error": True,
            "format": None,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

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
            entries = YouTubeTranscriptApi.get_transcript(vid)
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
