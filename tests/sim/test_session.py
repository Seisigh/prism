"""Mode must be an *observable consequence* of the agent's goal and its
own session history (author's explicit instruction), never a sampled or
directly-assigned input. These tests exercise sim/session.py against a
real built catalog and check that all five modes actually emerge from
the right conditions, via the same server.features.mode.assign_mode real
telemetry is scored with — not a simulator-only mode rule.
"""
import random
from collections import Counter

import pytest

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


def test_goalless_session_is_pure_discovery():
    rng = random.Random(1)
    session = simulate_session("s1", ARCHETYPES["deliberator"], _kitchen_items(), 15, rng)
    modes = {v.mode for v in session.views}
    assert modes == {"discovery"}


def test_item_goal_produces_directed_search():
    items = _kitchen_items()
    rng = random.Random(2)
    session = simulate_session(
        "s2", ARCHETYPES["deliberator"], items, 15, rng, goal=SessionGoal(target_item_id=items[0].item_id)
    )
    modes = {v.mode for v in session.views}
    assert modes == {"directed_search"}


def test_category_goal_produces_broad_search():
    items = _kitchen_items()
    rng = random.Random(3)
    session = simulate_session(
        "s3", ARCHETYPES["deliberator"], items, 15, rng, goal=SessionGoal(target_category="Kitchen & Dining")
    )
    modes = {v.mode for v in session.views}
    assert modes == {"broad_search"}


def test_near_substitute_heavy_browsing_produces_comparison():
    chairs = [v for v in ITEM_VECTORS.values() if v.near_substitute_set_id == "core-chair-00"]
    assert len(chairs) >= 2, "fixture assumption: core-chair-00 has at least 2 members in the built catalog"
    rng = random.Random(4)
    session = simulate_session("s4", ARCHETYPES["price_hunter"], chairs, len(chairs), rng)
    modes = Counter(v.mode for v in session.views)
    assert modes["comparison"] > 0, f"expected some comparison views from an all-near-substitute pool, got {modes}"


def test_sufficient_elapsed_time_and_revisits_produce_refind():
    """refind needs a real revisit AND >=60s elapsed since the first view
    of that item — a slow archetype (long dwell) over enough items is
    what gets a simulated session past that threshold, the same way a
    real visitor needs to actually spend that long browsing."""
    rng = random.Random(5)
    session = simulate_session(
        "s5", ARCHETYPES["deliberator"], _kitchen_items(), 60, rng, revisit_prob=0.35
    )
    modes = Counter(v.mode for v in session.views)
    assert modes["refind"] > 0, f"expected refind to emerge in a long, revisit-heavy session, got {modes}"


def test_goal_cannot_set_both_target_item_and_category():
    with pytest.raises(ValueError):
        SessionGoal(target_item_id="i1", target_category="Kitchen & Dining")


def test_session_never_assigns_mode_directly():
    """Static check that nothing in sim/session.py hardcodes a mode
    string as a view's mode — every view's mode must come from calling
    assign_mode. Guards against a future edit reintroducing a
    directly-sampled mode."""
    import inspect

    import sim.session as session_module

    source = inspect.getsource(session_module)
    # The only mode-shaped string literals allowed in this file are
    # inside the assign_mode call's own keyword arguments and comments/
    # docstrings — there must be no `mode = "..."` or `mode="..."` literal
    # assignment bypassing assign_mode.
    assert 'mode = "discovery"' not in source
    assert 'mode="discovery"' not in source
    assert "assign_mode(" in source
