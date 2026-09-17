import math
import random

import pytest

from server.models.taste_vector import (
    MIN_SCORED_VIEWS_FOR_OWN_VECTOR,
    TasteVectorTracker,
    clip,
    normalize,
    update,
    weight_from_calibrated_interest,
)

DIM = 4


def _norm(v: tuple[float, ...]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_normalize_zero_vector_raises():
    with pytest.raises(ValueError):
        normalize((0.0, 0.0, 0.0))


def test_normalize_produces_unit_norm():
    v = normalize((3.0, 4.0))
    assert math.isclose(_norm(v), 1.0, rel_tol=1e-9)


def test_weight_clip_bounds():
    assert weight_from_calibrated_interest(p_i=1.0, is_fast_skip=False) == 1.0
    assert weight_from_calibrated_interest(p_i=0.0, is_fast_skip=False) == -0.5
    assert weight_from_calibrated_interest(p_i=0.9, is_fast_skip=False) == clip(2 * 0.9 - 1, -0.5, 1.0)


def test_fast_skip_forces_negative_weight_regardless_of_p_i():
    assert weight_from_calibrated_interest(p_i=0.95, is_fast_skip=True) == -0.5


# --- required: unit norm after arbitrary update sequences -------------------


def test_unit_norm_after_arbitrary_update_sequence():
    rng = random.Random(0)
    v = normalize(tuple(rng.uniform(-1, 1) for _ in range(DIM)))
    for _ in range(200):
        e_i = normalize(tuple(rng.uniform(-1, 1) for _ in range(DIM)))
        w_i = rng.uniform(-0.5, 1.0)
        v = update(v, w_i, e_i)
        assert math.isclose(_norm(v), 1.0, rel_tol=1e-6, abs_tol=1e-9)


# --- required: bounded magnitude --------------------------------------------


def test_vector_never_exceeds_unit_magnitude_even_with_extreme_weights():
    rng = random.Random(1)
    v = normalize(tuple(rng.uniform(-1, 1) for _ in range(DIM)))
    for _ in range(500):
        e_i = normalize(tuple(rng.uniform(-1, 1) for _ in range(DIM)))
        w_i = rng.choice([-0.5, 1.0])  # extremes only
        v = update(v, w_i, e_i)
        assert _norm(v) <= 1.0 + 1e-9


# --- required: convergence into the correct region for a scripted sequence --


def test_convergence_toward_a_repeatedly_preferred_item_direction():
    """Repeatedly "liking" items near one direction in embedding space
    should pull the taste vector's cosine similarity to that direction up
    over time, starting from an unrelated centroid."""
    target_direction = normalize((1.0, 0.0, 0.0, 0.0))
    centroid = normalize((0.1, 1.0, 0.1, 0.1))  # far from target_direction initially
    tracker = TasteVectorTracker(catalog_centroid=centroid)

    rng = random.Random(2)

    def cosine_sim(a, b):
        return sum(x * y for x, y in zip(a, b))

    initial_sim = cosine_sim(tracker.vector, target_direction)

    for _ in range(30):
        # Items scattered near target_direction, each strongly liked.
        noisy = tuple(td + rng.uniform(-0.1, 0.1) for td in target_direction)
        item_embedding = normalize(noisy)
        tracker.observe_view(item_embedding, p_i=0.95, is_fast_skip=False)

    final_sim = cosine_sim(tracker.vector, target_direction)
    assert final_sim > initial_sim
    assert final_sim > 0.8, f"expected strong convergence toward the liked direction, got cosine={final_sim:.3f}"


def test_convergence_away_from_a_repeatedly_disliked_item_direction():
    target_direction = normalize((1.0, 0.0, 0.0, 0.0))
    centroid = normalize((1.0, 0.3, 0.0, 0.0))  # starts somewhat aligned
    tracker = TasteVectorTracker(catalog_centroid=centroid)
    rng = random.Random(4)

    def cosine_sim(a, b):
        return sum(x * y for x, y in zip(a, b))

    initial_sim = cosine_sim(tracker.vector, target_direction)
    for _ in range(30):
        noisy = tuple(td + rng.uniform(-0.05, 0.05) for td in target_direction)
        item_embedding = normalize(noisy)
        tracker.observe_view(item_embedding, p_i=0.0, is_fast_skip=False)  # strongly disliked -> weight -0.5

    final_sim = cosine_sim(tracker.vector, target_direction)
    assert final_sim < initial_sim


# --- population-prior gate ----------------------------------------------------


def test_population_prior_served_below_three_scored_views():
    centroid = normalize((1.0, 1.0, 1.0, 1.0))
    prior = normalize((0.0, 1.0, 0.0, 0.0))
    tracker = TasteVectorTracker(catalog_centroid=centroid)

    for i in range(MIN_SCORED_VIEWS_FOR_OWN_VECTOR - 1):
        tracker.observe_view(normalize((1.0, 0.0, 0.0, 0.0)), p_i=0.9, is_fast_skip=False)
        assert tracker.public_vector(prior) == prior


def test_own_vector_served_at_three_scored_views():
    centroid = normalize((1.0, 1.0, 1.0, 1.0))
    prior = normalize((0.0, 1.0, 0.0, 0.0))
    tracker = TasteVectorTracker(catalog_centroid=centroid)

    for _ in range(MIN_SCORED_VIEWS_FOR_OWN_VECTOR):
        tracker.observe_view(normalize((1.0, 0.0, 0.0, 0.0)), p_i=0.9, is_fast_skip=False)

    assert tracker.public_vector(prior) == tracker.vector
    assert tracker.public_vector(prior) != prior


def test_view_with_no_calibrated_interest_and_not_fast_skip_does_not_count():
    centroid = normalize((1.0, 1.0, 1.0, 1.0))
    tracker = TasteVectorTracker(catalog_centroid=centroid)
    tracker.observe_view(normalize((1.0, 0.0, 0.0, 0.0)), p_i=None, is_fast_skip=False)
    assert tracker.scored_view_count == 0


def test_fast_skip_view_counts_even_without_calibrated_interest():
    centroid = normalize((1.0, 1.0, 1.0, 1.0))
    tracker = TasteVectorTracker(catalog_centroid=centroid)
    tracker.observe_view(normalize((1.0, 0.0, 0.0, 0.0)), p_i=None, is_fast_skip=True)
    assert tracker.scored_view_count == 1
