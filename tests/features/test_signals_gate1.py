"""Gate 1 signal additions (server/features/signals_gate1.py). The three
pointer-based signals (pause_count, acceleration_profile, focused_idle)
get the same leakage-audit treatment as the Gate 0 registry in
test_leakage.py, since they read `events` the same way. The three
session-context signals (revisit_count, category_breadth,
query_specificity) read only `ItemContext`'s Gate-1 fields, so what's
tested there is correctness of the value and the "0 is a real value, not
missingness" distinction, not event-window leakage.
"""
from server.features.signals import ItemContext
from server.features.signals_gate1 import (
    GATE1_SIGNAL_REGISTRY,
    category_breadth,
    focused_idle,
    query_specificity,
    revisit_count,
)
from server.features.window_spec import RawEvent, WindowSpec

WINDOW = WindowSpec(t_start=0.0, t_end=2000.0, seal_reason="view_close")
CTX = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")

POINTER_SIGNALS = ["pause_count", "acceleration_profile", "focused_idle"]


def _baseline_events_with_a_pause() -> list[RawEvent]:
    # Moves, then sits still for a long stretch (a pause / focused idle
    # period), then moves again -- built to exercise all three pointer
    # signals with a legitimate non-None value.
    events = []
    moving = [(0, 0, 0), (100, 40, 20), (200, 80, 40)]
    still = [(200, 80, 40), (400, 81, 40), (600, 80, 41), (800, 80, 40)]
    moving_again = [(800, 80, 40), (900, 150, 100), (1000, 220, 160)]
    for t, x, y in moving + still + moving_again:
        events.append(RawEvent(t=float(t), type="pointer_sample", item_id="i1", surface="detail", payload={"x": x, "y": y}))
    return events


def _poison_events(seal_t: float) -> list[RawEvent]:
    poison = []
    for offset in (0.0, 5000.0):
        t = seal_t + offset
        poison.append(RawEvent(t=t, type="pointer_sample", item_id="i1", surface="detail", payload={"x": 999999, "y": -999999}))
    return poison


def test_pointer_signals_produce_a_legitimate_value_on_the_baseline():
    baseline = _baseline_events_with_a_pause()
    for name in POINTER_SIGNALS:
        value = GATE1_SIGNAL_REGISTRY[name](baseline, WINDOW, CTX)
        assert value is not None, f"{name} returned None on a baseline built to exercise it"


def test_pointer_signals_blind_to_events_at_or_after_seal():
    baseline = _baseline_events_with_a_pause()
    poisoned = baseline + _poison_events(WINDOW.t_end)
    for name in POINTER_SIGNALS:
        fn = GATE1_SIGNAL_REGISTRY[name]
        assert fn(poisoned, WINDOW, CTX) == fn(baseline, WINDOW, CTX), f"{name} read past its window"


def test_pointer_signals_gated_off_for_touch():
    touch_ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="touch")
    baseline = _baseline_events_with_a_pause()
    for name in POINTER_SIGNALS:
        assert GATE1_SIGNAL_REGISTRY[name](baseline, WINDOW, touch_ctx) is None


def test_pause_count_counts_a_single_low_velocity_stretch_once():
    baseline = _baseline_events_with_a_pause()
    value = GATE1_SIGNAL_REGISTRY["pause_count"](baseline, WINDOW, CTX)
    assert value == 1.0


def test_revisit_count_is_zero_not_none_with_no_prior_views():
    ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")
    assert revisit_count([], WINDOW, ctx) == 0.0


def test_revisit_count_counts_prior_views_of_this_item():
    ctx = ItemContext(
        item_id="i1", surface="detail", mode="discovery", pointer_type="mouse",
        prior_view_starts_for_item=(-5000.0, -2000.0),
    )
    assert revisit_count([], WINDOW, ctx) == 2.0


def test_category_breadth_counts_current_item_when_no_prior_history():
    ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse", category="Kitchen & Dining")
    assert category_breadth([], WINDOW, ctx) == 1.0


def test_category_breadth_deduplicates_repeated_categories():
    ctx = ItemContext(
        item_id="i1", surface="detail", mode="discovery", pointer_type="mouse",
        category="Kitchen & Dining",
        prior_view_categories=("Kitchen & Dining", "Kitchen & Dining", "Office"),
    )
    assert category_breadth([], WINDOW, ctx) == 2.0


def test_category_breadth_none_when_category_unknown():
    ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")
    assert category_breadth([], WINDOW, ctx) is None


def test_query_specificity_none_with_no_active_query():
    ctx = ItemContext(item_id="i1", surface="search", mode="discovery", pointer_type="mouse")
    assert query_specificity([], WINDOW, ctx) is None


def test_query_specificity_increases_with_token_count():
    low = ItemContext(item_id="i1", surface="search", mode="broad_search", pointer_type="mouse", active_query_token_count=1)
    high = ItemContext(item_id="i1", surface="search", mode="directed_search", pointer_type="mouse", active_query_token_count=4)
    v_low = query_specificity([], WINDOW, low)
    v_high = query_specificity([], WINDOW, high)
    assert v_low is not None and v_high is not None
    assert v_high > v_low


def test_near_substitute_coview_count_none_without_a_substitute_set():
    from server.features.signals_gate1 import near_substitute_coview_count

    ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")
    assert near_substitute_coview_count([], WINDOW, ctx) is None


def test_near_substitute_coview_count_reports_caller_supplied_count():
    from server.features.signals_gate1 import near_substitute_coview_count

    ctx = ItemContext(
        item_id="i1", surface="detail", mode="comparison", pointer_type="mouse",
        near_substitute_coview_count=2,
    )
    assert near_substitute_coview_count([], WINDOW, ctx) == 2.0
