"""eval/features.py: the bridge from a simulated session to per-view
composite feature rows, running the real server/features/ pipeline."""
import random

import pytest

from eval.features import ALL_SIGNALS, extract_session_features
from sim.agents import ARCHETYPES
from sim.embedding import build_item_vectors
from sim.session import SessionGoal, simulate_session

try:
    ITEM_VECTORS = build_item_vectors()
except FileNotFoundError:
    ITEM_VECTORS = None

pytestmark = pytest.mark.skipif(ITEM_VECTORS is None, reason="data/catalog.json not built — run `python -m catalog.build`")


def _kitchen_items():
    return [v for v in ITEM_VECTORS.values() if v.category == "Kitchen & Dining"]


def test_extract_produces_one_row_per_view():
    rng = random.Random(1)
    session = simulate_session("s1", ARCHETYPES["deliberator"], _kitchen_items(), 15, rng)
    rows = extract_session_features(session, ITEM_VECTORS)
    assert len(rows) == len(session.views)


def test_every_row_carries_all_families_including_directional():
    rng = random.Random(2)
    session = simulate_session("s2", ARCHETYPES["skimmer"], _kitchen_items(), 15, rng)
    rows = extract_session_features(session, ITEM_VECTORS)
    for row in rows:
        assert set(row.composites.keys()) == {
            "attention", "motor_conflict", "exploration", "comparison", "directional", "availability",
        }
        assert set(row.availability.keys()) == set(row.composites.keys())


def test_every_row_carries_every_raw_signal_by_name():
    """The ranker's actual feature set (eval/ranker.py): one normalized
    value per registered signal, not folded into a composite."""
    rng = random.Random(2)
    session = simulate_session("s2b", ARCHETYPES["skimmer"], _kitchen_items(), 15, rng)
    rows = extract_session_features(session, ITEM_VECTORS)
    for row in rows:
        assert set(row.signals.keys()) == set(ALL_SIGNALS.keys())


def test_utility_is_carried_through_unmodified_for_evaluation_only():
    rng = random.Random(3)
    session = simulate_session("s3", ARCHETYPES["price_hunter"], _kitchen_items(), 15, rng)
    rows = extract_session_features(session, ITEM_VECTORS)
    by_item = {v.item_id: v.utility for v in session.views}
    for row in rows:
        assert row.utility == by_item[row.item_id]


def test_directed_search_session_has_query_specificity_signal_available():
    items = _kitchen_items()
    rng = random.Random(4)
    session = simulate_session(
        "s4", ARCHETYPES["deliberator"], items, 15, rng, goal=SessionGoal(target_item_id=items[0].item_id)
    )
    rows = extract_session_features(session, ITEM_VECTORS)
    assert all(row.mode == "directed_search" for row in rows)
    # availability of exploration's constituents (which include
    # query_specificity) should be > 0 for at least one row.
    assert any(row.availability["exploration"] > 0 for row in rows)


def test_revisit_produces_nonzero_comparison_availability():
    rng = random.Random(5)
    session = simulate_session(
        "s5", ARCHETYPES["deliberator"], _kitchen_items(), 60, rng, revisit_prob=0.35
    )
    rows = extract_session_features(session, ITEM_VECTORS)
    refind_rows = [r for r in rows if r.mode == "refind"]
    assert refind_rows, "expected some refind views in this long, revisit-heavy session"
    assert any(r.availability["comparison"] > 0 for r in refind_rows)
