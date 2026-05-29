"""Both platforms converge to one VideoMetadata schema (FR-4)."""
import datetime as dt

from app.ingest.base import RawMetadata
from app.ingest.normalize import normalize


def test_normalize_maps_fields_and_assigns_slot():
    raw = RawMetadata(
        source="instagram",
        url="https://instagram.com/reel/abc",
        creator="creator_b",
        follower_count=12000,
        views=80000,
        likes=4000,
        comments=600,
        hashtags=["fyp", "tips"],
        upload_date=dt.date(2026, 1, 2),
        duration=22.0,
        caption="hello #fyp #tips",
        media_url="https://cdn/x.mp4",
    )
    meta = normalize(raw, "B")
    assert meta.video_id == "B"
    assert meta.source == "instagram"
    assert meta.creator == "creator_b"
    assert meta.hashtags == ["fyp", "tips"]
    # engagement_rate derived: (4000+600)/80000*100 = 5.75
    assert meta.engagement_rate == 5.75
