"""server/recommender/policy.py: epsilon-greedy with a permanent
random-policy session fraction, and propensity logging."""
import random

from server.recommender.catalog_view import CatalogItem
from server.recommender.policy import is_random_policy_session, recommend


def _item(item_id, vector) -> CatalogItem:
    return CatalogItem(item_id=item_id, category="Kitchen & Dining", price_cents=1000, price_band=0, vector=vector)


def test_is_random_policy_session_is_stable_for_the_same_session_id():
    assert is_random_policy_session("s1") == is_random_policy_session("s1")


def test_is_random_policy_session_fraction_is_approximately_right_across_many_sessions():
    n = 20000
    random_count = sum(1 for i in range(n) if is_random_policy_session(f"session-{i}"))
    rate = random_count / n
    assert 0.03 < rate < 0.07  # target 0.05, generous tolerance for hash-based assignment


def test_recommend_always_returns_a_propensity_per_item():
    candidates = {f"i{i}": _item(f"i{i}", (float(i), 1.0)) for i in range(10)}
    rng = random.Random(0)
    slate = recommend("normal-session", (1.0, 0.0), candidates, k=5, rng=rng)
    assert len(slate.item_ids) == len(slate.propensities) == 5
    assert all(0.0 < p <= 1.0 for p in slate.propensities)


def test_recommend_never_returns_an_item_twice_in_one_slate():
    candidates = {f"i{i}": _item(f"i{i}", (float(i), 1.0)) for i in range(10)}
    rng = random.Random(1)
    slate = recommend("normal-session", (1.0, 0.0), candidates, k=8, rng=rng, epsilon=0.5)
    assert len(set(slate.item_ids)) == len(slate.item_ids)


def test_recommend_on_a_random_policy_session_ignores_the_taste_vector():
    """A session hashed into the permanent random-policy fraction must
    get policy_id='random' regardless of epsilon, and its propensities
    must be exact sequential-without-replacement values."""
    candidates = {f"i{i}": _item(f"i{i}", (float(i), 1.0)) for i in range(10)}
    random_session_id = next(f"s{i}" for i in range(100000) if is_random_policy_session(f"s{i}"))
    rng = random.Random(2)
    slate = recommend(random_session_id, (1.0, 0.0), candidates, k=4, rng=rng, epsilon=0.0)
    assert slate.policy_id == "random"
    assert slate.propensities == [1 / 10, 1 / 9, 1 / 8, 1 / 7]


def test_recommend_zero_epsilon_on_a_normal_session_reproduces_pure_mmr():
    from server.recommender.mmr import mmr_rerank, rank_by_cosine

    candidates = {f"i{i}": _item(f"i{i}", (float(i), 1.0)) for i in range(10)}
    taste = (5.0, 1.0)
    normal_session_id = next(f"s{i}" for i in range(100000) if not is_random_policy_session(f"s{i}"))
    rng = random.Random(3)
    slate = recommend(normal_session_id, taste, candidates, k=4, rng=rng, epsilon=0.0)
    expected = mmr_rerank(rank_by_cosine(taste, candidates), candidates, 4)
    assert slate.item_ids == expected
    assert all(p == 1.0 for p in slate.propensities)


def test_recommend_empty_candidates_returns_empty_slate_not_a_crash():
    rng = random.Random(4)
    slate = recommend("s1", (1.0, 0.0), {}, k=5, rng=rng)
    assert slate.item_ids == [] and slate.propensities == []
