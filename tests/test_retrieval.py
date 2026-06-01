"""Balanced retrieval: a comparison must always see both videos (not just the
video whose chunks happen to sit nearest the query)."""
from dataclasses import dataclass

from app.rag.retrieval import _balance_by_video


@dataclass
class _Chunk:
    chunk_id: int
    video_id: str


def _rows(spec):
    """spec: list of (chunk_id, video_id, distance), assumed distance-sorted."""
    return [(_Chunk(cid, vid), dist) for cid, vid, dist in spec]


def test_both_videos_represented_when_one_dominates_nearest():
    # The 4 nearest chunks are all Video A; a naive top-k=4 would drop B.
    rows = _rows([
        (1, "A", 0.10),
        (2, "A", 0.12),
        (3, "A", 0.15),
        (4, "A", 0.18),
        (5, "B", 0.40),
        (6, "B", 0.42),
    ])
    picked = _balance_by_video(rows, k=4)
    vids = {c.video_id for c, _ in picked}
    assert vids == {"A", "B"}, "both videos must appear in a comparison context"
    assert len(picked) == 4


def test_nearest_first_within_budget():
    rows = _rows([
        (1, "A", 0.10),
        (2, "B", 0.20),
        (3, "A", 0.30),
        (4, "B", 0.40),
    ])
    picked = _balance_by_video(rows, k=2)
    # Round-robin takes A's nearest then B's nearest; result is distance-sorted.
    assert [c.chunk_id for c, _ in picked] == [1, 2]


def test_result_sorted_by_distance():
    rows = _rows([(1, "A", 0.1), (2, "B", 0.2), (3, "A", 0.3), (4, "B", 0.4)])
    picked = _balance_by_video(rows, k=4)
    dists = [d for _, d in picked]
    assert dists == sorted(dists)


def test_single_video_corpus_still_returns_k():
    rows = _rows([(1, "A", 0.1), (2, "A", 0.2), (3, "A", 0.3)])
    picked = _balance_by_video(rows, k=2)
    assert len(picked) == 2
    assert {c.video_id for c, _ in picked} == {"A"}


def test_empty_candidates():
    assert _balance_by_video([], k=4) == []
