"""Seed a realistic YouTube + Instagram pair WITHOUT the fragile live extraction.

Lets the full downstream path (chunk → BGE embed → pgvector store → router →
retrieval → synthesis) be exercised deterministically. Live ingestion via
yt-dlp/instaloader needs real public URLs and rate-limits; this is the
demo-stable substitute. Run: `uv run python -m scripts.seed`.
"""
from __future__ import annotations

import datetime as dt

from app.core.db import SessionLocal, init_db
from app.ingest.base import TranscriptSegment
from app.ingest.pipeline import _persist
from app.models.video import VideoMetadata

# --- Video A: YouTube. Strong, direct hook; higher engagement. ---
A_META = VideoMetadata(
    video_id="A",
    source="youtube",
    url="https://youtube.com/shorts/demoA",
    creator="ChefMarco",
    follower_count=820_000,
    views=500_000,
    likes=45_000,
    comments=3_000,
    hashtags=["steak", "cooking", "kitchentips"],
    upload_date=dt.date(2026, 4, 12),
    duration=38.0,
    title="The 3-second rule for a perfect steak",
)
A_SEGMENTS = [
    TranscriptSegment("Stop overcooking your steak.", 0.0, 1.8),
    TranscriptSegment("Here's the three second rule chefs swear by.", 1.8, 4.6),
    TranscriptSegment("Press the steak with your finger.", 5.2, 7.4),
    TranscriptSegment("If it springs back fast, it's medium rare.", 7.4, 10.5),
    TranscriptSegment("Rest it for five minutes before you cut.", 11.0, 14.0),
    TranscriptSegment("That locks in all the juices.", 14.0, 16.5),
    TranscriptSegment("Try it tonight and tag me in your results.", 30.0, 34.0),
]

# --- Video B: Instagram Reel. Weak generic intro; lower engagement. ---
B_META = VideoMetadata(
    video_id="B",
    source="instagram",
    url="https://instagram.com/reel/demoB",
    creator="homecook_jen",
    follower_count=54_000,
    views=200_000,
    likes=8_000,
    comments=400,
    hashtags=["food", "reels", "cooking"],
    upload_date=dt.date(2026, 4, 20),
    duration=44.0,
    caption="A little steak tutorial for you all 🥩 #food #reels #cooking",
)
B_SEGMENTS = [
    TranscriptSegment("Hey guys, welcome back to my page.", 0.0, 2.5),
    TranscriptSegment("Today we're gonna talk about cooking a steak.", 2.5, 5.5),
    TranscriptSegment("So first you wanna get a pan really hot.", 6.0, 9.0),
    TranscriptSegment("Add some oil, and then put the steak in.", 9.0, 12.5),
    TranscriptSegment("Cook it for a while on each side.", 13.0, 16.0),
    TranscriptSegment("And um, yeah, that's basically it.", 25.0, 28.0),
    TranscriptSegment("Don't forget to like and follow for more.", 40.0, 43.5),
]


def main() -> None:
    init_db()
    with SessionLocal() as session:
        _persist(session, A_META, A_SEGMENTS)
        _persist(session, B_META, B_SEGMENTS)
    print("Seeded videos A (YouTube) and B (Instagram) with transcripts + chunks.")


if __name__ == "__main__":
    main()
