"""Local transcription via faster-whisper.

Runs ONLY on the Instagram path, since Instagram provides no transcript while
YouTube hands one over for free. No per-minute API bill (README).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import get_settings
from app.ingest.base import TranscriptSegment


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    # int8 on CPU keeps it light for the demo volume.
    return WhisperModel(
        get_settings().whisper_model, device="cpu", compute_type="int8"
    )


def transcribe(media_path: Path) -> list[TranscriptSegment]:
    segments, _info = _model().transcribe(str(media_path), vad_filter=True)
    return [
        TranscriptSegment(
            text=s.text.strip(), start=float(s.start), end=float(s.end)
        )
        for s in segments
        if s.text.strip()
    ]
