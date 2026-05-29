"""Local BGE embeddings via sentence-transformers (CPU, $0).

BGE recommends an instruction prefix on the *query* side for retrieval; passages
are embedded as-is. Cosine similarity is used downstream, so vectors are
normalized.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

# Prefix BGE expects on retrieval queries (not on stored passages).
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model, device="cpu")


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed transcript chunks for storage."""
    if not texts:
        return []
    vecs = _model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    )
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    """Embed a user query with the BGE retrieval instruction prefix."""
    vec = _model().encode(
        _QUERY_INSTRUCTION + text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec.tolist()
