"""Transcription for the Instagram path (Instagram provides no transcript).

Two interchangeable providers, selected by `TRANSCRIBE_PROVIDER`:
  - "groq"  — hosted Whisper (whisper-large-v3-turbo). A ~1s API call; by far
              the fastest option and the demo default. Reuses the Groq LLM key.
  - "local" — faster-whisper on CPU. No API bill, but minutes per clip; the
              README's "transcription saturates first" bottleneck.
Both return the same list[TranscriptSegment] with start/end timestamps, so the
hook chunk (segments with start < 5s) works regardless of provider.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.ingest.base import TranscriptSegment


# ---- Groq hosted Whisper (default) ----

@lru_cache(maxsize=1)
def _groq_client():
    from openai import OpenAI

    from app.rag.llm import _http_clients  # reuse the IPv4-forced sync client

    s = get_settings()
    sync_client, _ = _http_clients()
    return OpenAI(
        api_key=s.llm_api_key, base_url=s.llm_base_url, http_client=sync_client
    )


def _groq_transcribe(media_path: Path) -> list[TranscriptSegment]:
    s = get_settings()
    with open(media_path, "rb") as f:
        resp = _groq_client().audio.transcriptions.create(
            file=f,
            model=s.groq_whisper_model,
            response_format="verbose_json",  # includes per-segment timestamps
            timestamp_granularities=["segment"],
        )
    segments = getattr(resp, "segments", None) or []
    out: list[TranscriptSegment] = []
    for seg in segments:
        # SDK returns pydantic objects or dicts depending on version. Use an
        # explicit getter — not `or` — since start=0.0 is valid but falsy.
        get = seg.get if isinstance(seg, dict) else lambda k, d=None: getattr(seg, k, d)
        text = (get("text", "") or "").strip()
        if not text:
            continue
        start = float(get("start", 0.0) or 0.0)
        end = float(get("end", start) or start)
        out.append(TranscriptSegment(text=text, start=start, end=end))
    # Fallback: if no segments came back, use the flat text as one segment.
    if not out and getattr(resp, "text", "").strip():
        out.append(TranscriptSegment(text=resp.text.strip(), start=0.0, end=0.0))
    return out


# ---- Local faster-whisper (fallback) ----

@lru_cache(maxsize=1)
def _local_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        get_settings().whisper_model, device="cpu", compute_type="int8"
    )


def _local_transcribe(media_path: Path) -> list[TranscriptSegment]:
    # beam_size=1 (greedy) is ~2-3x faster than the default beam search with
    # negligible quality loss on short clips; vad_filter skips silence.
    segments, _info = _local_model().transcribe(
        str(media_path), beam_size=1, vad_filter=True
    )
    return [
        TranscriptSegment(text=s.text.strip(), start=float(s.start), end=float(s.end))
        for s in segments
        if s.text.strip()
    ]


def transcribe(media_path: Path) -> list[TranscriptSegment]:
    if get_settings().transcribe_provider.lower() == "local":
        return _local_transcribe(media_path)
    return _groq_transcribe(media_path)
