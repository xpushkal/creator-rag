"""Engagement rate must be exact, every time (NFR-1)."""
from app.models.video import VideoMetadata, compute_engagement_rate


def test_basic_engagement_rate():
    # (50000 + 1000) / 200000 * 100 = 25.5
    assert compute_engagement_rate(50000, 1000, 200000) == 25.5


def test_zero_views_is_none():
    assert compute_engagement_rate(10, 5, 0) is None


def test_none_views_is_none():
    assert compute_engagement_rate(10, 5, None) is None


def test_missing_likes_comments_treated_as_zero():
    assert compute_engagement_rate(None, None, 100) == 0.0


def test_computed_field_on_metadata():
    v = VideoMetadata(
        video_id="A", source="youtube", url="http://x",
        likes=300, comments=200, views=1000,
    )
    assert v.engagement_rate == 50.0
