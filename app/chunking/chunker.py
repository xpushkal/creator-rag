"""Transcript chunking tuned for short-form video (README "Chunking").

Short-form transcripts are tiny (often 100-300 words). Over-chunking produces
near-duplicate chunks that pollute retrieval; under-chunking loses granularity.
Landing spot: sentence-window chunks of ~250 tokens with ~15% overlap, PLUS a
dedicated hook chunk built from every segment with start < 5s, so the
"compare the first 5 seconds" question (UC-3) retrieves cleanly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingest.base import TranscriptSegment
from app.models.chunk import MODALITY_HOOK, MODALITY_TRANSCRIPT

TARGET_TOKENS = 250
OVERLAP_RATIO = 0.15
HOOK_WINDOW_SECONDS = 5.0

# Whisper hallucinates short filler on music/silence ("Thank you", "Thanks for
# watching"). A transcript below these thresholds is treated as "no usable
# speech" and produces no chunks, so fabricated text never becomes retrievable
# evidence. Real short-form speech easily clears these.
MIN_TRANSCRIPT_WORDS = 5
MIN_UNIQUE_WORDS = 4

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z0-9']+")


def has_usable_speech(segments: list[TranscriptSegment]) -> bool:
    words = _WORD_RE.findall(" ".join(s.text for s in segments).lower())
    return len(words) >= MIN_TRANSCRIPT_WORDS and len(set(words)) >= MIN_UNIQUE_WORDS


@dataclass
class TranscriptChunk:
    text: str
    modality: str
    start: float | None
    end: float | None


def _estimate_tokens(text: str) -> int:
    # Cheap, dependency-free heuristic: ~0.75 words per token.
    words = len(text.split())
    return max(1, round(words / 0.75))


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _build_hook_chunk(segments: list[TranscriptSegment]) -> TranscriptChunk | None:
    """All speech in the first HOOK_WINDOW_SECONDS, as one retrievable chunk."""
    hook = [s for s in segments if s.start < HOOK_WINDOW_SECONDS]
    if not hook:
        return None
    return TranscriptChunk(
        text=" ".join(s.text for s in hook).strip(),
        modality=MODALITY_HOOK,
        start=min(s.start for s in hook),
        end=max(s.end for s in hook),
    )


def _sentence_window_chunks(
    segments: list[TranscriptSegment],
) -> list[TranscriptChunk]:
    """Greedy sentence packing to ~TARGET_TOKENS with ~OVERLAP_RATIO carryover.

    Each sentence keeps the timestamp of the segment it came from so chunks stay
    citable with a start/end window.
    """
    # Flatten to (sentence, start, end), splitting multi-sentence segments.
    sentences: list[tuple[str, float, float]] = []
    for seg in segments:
        parts = _split_sentences(seg.text) or [seg.text]
        for p in parts:
            sentences.append((p, seg.start, seg.end))

    chunks: list[TranscriptChunk] = []
    cur: list[tuple[str, float, float]] = []
    cur_tokens = 0
    overlap_tokens = round(TARGET_TOKENS * OVERLAP_RATIO)

    def flush() -> None:
        nonlocal cur, cur_tokens
        if not cur:
            return
        chunks.append(
            TranscriptChunk(
                text=" ".join(s for s, _, _ in cur).strip(),
                modality=MODALITY_TRANSCRIPT,
                start=cur[0][1],
                end=cur[-1][2],
            )
        )
        # Carry a tail of sentences for ~OVERLAP_RATIO continuity.
        carry: list[tuple[str, float, float]] = []
        t = 0
        for s in reversed(cur):
            t += _estimate_tokens(s[0])
            carry.insert(0, s)
            if t >= overlap_tokens:
                break
        cur = carry
        cur_tokens = sum(_estimate_tokens(s[0]) for s in cur)

    for sent in sentences:
        tok = _estimate_tokens(sent[0])
        if cur and cur_tokens + tok > TARGET_TOKENS:
            flush()
        cur.append(sent)
        cur_tokens += tok
    # Final flush without re-carrying.
    if cur:
        chunks.append(
            TranscriptChunk(
                text=" ".join(s for s, _, _ in cur).strip(),
                modality=MODALITY_TRANSCRIPT,
                start=cur[0][1],
                end=cur[-1][2],
            )
        )
    return chunks


def chunk_transcript(segments: list[TranscriptSegment]) -> list[TranscriptChunk]:
    """Produce transcript chunks plus a dedicated hook chunk (if any speech in
    the first 5 seconds). Returns [] when there's no usable speech, so Whisper
    hallucinations on music/silence don't become retrievable evidence."""
    if not segments or not has_usable_speech(segments):
        return []
    chunks = _sentence_window_chunks(segments)
    hook = _build_hook_chunk(segments)
    if hook:
        chunks.insert(0, hook)
    return chunks
