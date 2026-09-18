"""server/recommender/mmr.py: cosine ranking and MMR diversity re-ranking."""
from server.recommender.catalog_view import CatalogItem
from server.recommender.mmr import cosine_similarity, mmr_rerank, rank_by_cosine


def _item(item_id, vector, category="Kitchen & Dining", price_cents=1000) -> CatalogItem:
    return CatalogItem(item_id=item_id, category=category, price_cents=price_cents, price_band=0, vector=vector)


def test_cosine_similarity_of_identical_vectors_is_one():
    assert abs(cosine_similarity((1.0, 0.0), (1.0, 0.0)) - 1.0) < 1e-9


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert abs(cosine_similarity((1.0, 0.0), (0.0, 1.0))) < 1e-9


def test_cosine_similarity_zero_vector_is_zero_not_a_crash():
    assert cosine_similarity((0.0, 0.0), (1.0, 1.0)) == 0.0


def test_rank_by_cosine_orders_closest_first():
    candidates = {
        "close": _item("close", (0.9, 0.1)),
        "far": _item("far", (0.1, 0.9)),
    }
    ranked = rank_by_cosine((1.0, 0.0), candidates)
    assert [item_id for item_id, _ in ranked] == ["close", "far"]


def test_mmr_rerank_prefers_diverse_items_over_a_near_duplicate():
    """Two items nearly identical to the taste vector, one item less
    relevant but distinct -- with diversity pressure, MMR should not
    pick both near-duplicates back to back."""
    candidates = {
        "a": _item("a", (1.0, 0.0, 0.0)),
        "b": _item("b", (0.99, 0.01, 0.0)),  # near-duplicate of a
        "c": _item("c", (0.0, 1.0, 0.0)),  # distinct, less relevant
    }
    taste = (1.0, 0.0, 0.0)
    ranked = rank_by_cosine(taste, candidates)
    assert ranked[0][0] == "a"  # most relevant is a, as expected

    diverse_slate = mmr_rerank(ranked, candidates, k=2, diversity_lambda=0.3)
    assert diverse_slate[0] == "a"
    assert diverse_slate[1] == "c", f"expected diversity to prefer 'c' over near-duplicate 'b', got {diverse_slate}"


def test_mmr_rerank_with_diversity_lambda_one_is_pure_relevance():
    candidates = {
        "a": _item("a", (1.0, 0.0, 0.0)),
        "b": _item("b", (0.99, 0.01, 0.0)),
        "c": _item("c", (0.0, 1.0, 0.0)),
    }
    ranked = rank_by_cosine((1.0, 0.0, 0.0), candidates)
    slate = mmr_rerank(ranked, candidates, k=3, diversity_lambda=1.0)
    assert slate == [item_id for item_id, _ in ranked]


def test_mmr_rerank_returns_fewer_than_k_when_pool_is_smaller():
    candidates = {"a": _item("a", (1.0, 0.0))}
    ranked = rank_by_cosine((1.0, 0.0), candidates)
    assert mmr_rerank(ranked, candidates, k=5) == ["a"]
