"""Chunking behavior: hook chunk from start<5s, plus sentence-window transcript."""
from app.ingest.base import TranscriptSegment
from app.chunking.chunker import (
    HOOK_WINDOW_SECONDS,
    chunk_transcript,
)
from app.models.chunk import MODALITY_HOOK, MODALITY_TRANSCRIPT


def _segments():
    return [
        TranscriptSegment("Stop scrolling right now.", 0.0, 2.0),
        TranscriptSegment("Here is the one trick.", 2.0, 4.5),
        TranscriptSegment("First you open the app.", 6.0, 9.0),
        TranscriptSegment("Then you tap the button.", 9.0, 12.0),
    ]


def test_empty_returns_no_chunks():
    assert chunk_transcript([]) == []


def test_hook_chunk_built_from_first_five_seconds():
    chunks = chunk_transcript(_segments())
    hooks = [c for c in chunks if c.modality == MODALITY_HOOK]
    assert len(hooks) == 1
    hook = hooks[0]
    # Only the < 5s speech, in order.
    assert "Stop scrolling" in hook.text
    assert "one trick" in hook.text
    assert "open the app" not in hook.text
    assert hook.start < HOOK_WINDOW_SECONDS


def test_transcript_chunks_present():
    chunks = chunk_transcript(_segments())
    transcript = [c for c in chunks if c.modality == MODALITY_TRANSCRIPT]
    assert transcript
    # All transcript text is covered somewhere.
    joined = " ".join(c.text for c in transcript)
    assert "open the app" in joined
    assert "tap the button" in joined


def test_no_hook_when_no_early_speech():
    late = [TranscriptSegment("Way past the hook window.", 10.0, 13.0)]
    chunks = chunk_transcript(late)
    assert all(c.modality != MODALITY_HOOK for c in chunks)
