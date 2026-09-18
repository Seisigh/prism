"""Candidate ranking (exact cosine on the taste vector) and MMR diversity
re-ranking (BUILD_BRIEF.md §12: "Candidate generation by exact cosine on
the taste vector with category and price-band filters. MMR diversity.").
"""
from __future__ import annotations

import math

from server.recommender.catalog_view import CatalogItem


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_cosine(taste_vector: tuple[float, ...], candidates: dict[str, CatalogItem]) -> list[tuple[str, float]]:
    """Descending by cosine similarity to `taste_vector` -- ties broken
    by item_id for determinism (tests rely on this)."""
    scored = [(item_id, cosine_similarity(taste_vector, item.vector)) for item_id, item in candidates.items()]
    return sorted(scored, key=lambda kv: (-kv[1], kv[0]))


def mmr_rerank(
    ranked: list[tuple[str, float]],
    candidates: dict[str, CatalogItem],
    k: int,
    diversity_lambda: float = 0.5,
) -> list[str]:
    """Standard maximal-marginal-relevance selection: iteratively pick
    the candidate maximizing `diversity_lambda * relevance -
    (1 - diversity_lambda) * max_similarity_to_already_selected`.
    `diversity_lambda=1.0` degenerates to pure relevance ranking (no
    diversity pressure); lower values push harder toward variety."""
    remaining = dict(ranked)
    selected: list[str] = []
    while remaining and len(selected) < k:
        best_id, best_mmr = None, float("-inf")
        for item_id, relevance in remaining.items():
            max_sim = max((cosine_similarity(candidates[item_id].vector, candidates[s].vector) for s in selected), default=0.0)
            mmr = diversity_lambda * relevance - (1 - diversity_lambda) * max_sim
            if mmr > best_mmr or (mmr == best_mmr and (best_id is None or item_id < best_id)):
                best_mmr, best_id = mmr, item_id
        selected.append(best_id)
        del remaining[best_id]
    return selected
