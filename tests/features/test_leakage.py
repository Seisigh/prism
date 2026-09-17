"""The leakage audit (§10.8): table-driven over every registered signal,
build-failing on violation. For each signal function, computes its output
against a baseline event set, then recomputes with "poison" events
injected at and after the window seal — events deliberately shaped to
swing the output hard if they were ever read (a huge pointer jump, a
scroll to the bottom of the page, an hour-long hover). If the output
changes, the function read something it shouldn't have.
"""
import pytest

from server.features.signals import SIGNAL_REGISTRY, ItemContext
from server.features.window_spec import RawEvent, WindowSpec, events_in_window

WINDOW = WindowSpec(t_start=0.0, t_end=2000.0, seal_reason="view_close")
CTX = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")


def _baseline_events() -> list[RawEvent]:
    events = []
    # Pointer samples: a mild wandering path so curvature/velocity/flips
    # all produce legitimate non-None values.
    xs = [(0, 0), (300, 40), (600, 20), (900, 60), (1200, 30), (1500, 70)]
    for t, x in xs:
        events.append(RawEvent(t=float(t), type="pointer_sample", item_id="i1", surface="detail", payload={"x": x, "y": x * 0.5}))
    # Scroll samples with a reversal.
    for t, y in [(100, 0.1), (500, 0.4), (900, 0.2), (1300, 0.6)]:
        events.append(RawEvent(t=float(t), type="scroll_sample", item_id=None, surface="detail", payload={"y_ratio": y}))
    # Hover start/end pair.
    events.append(RawEvent(t=200.0, type="hover_start", item_id="i1", surface="detail", payload={}))
    events.append(RawEvent(t=800.0, type="hover_end", item_id="i1", surface="detail", payload={}))
    # Visibility samples, mostly visible.
    for t, ratio in [(0, 0.9), (1000, 0.9), (1900, 0.9)]:
        events.append(RawEvent(t=float(t), type="visibility_sample", item_id="i1", surface="detail", payload={"ratio": ratio}))
    return events


def _poison_events(seal_t: float) -> list[RawEvent]:
    """Events at exactly the seal and shortly after it, each shaped to
    blow up the corresponding signal's value if it were ever admitted."""
    poison = []
    for offset, label in [(0.0, "at_seal"), (5000.0, "after_seal")]:
        t = seal_t + offset
        poison += [
            RawEvent(t=t, type="pointer_sample", item_id="i1", surface="detail", payload={"x": 999999, "y": -999999}),
            RawEvent(t=t, type="scroll_sample", item_id=None, surface="detail", payload={"y_ratio": 1.0}),
            RawEvent(t=t, type="hover_start", item_id="i1", surface="detail", payload={}),
            RawEvent(t=t + 100000, type="hover_end", item_id="i1", surface="detail", payload={}),
            RawEvent(t=t, type="visibility_sample", item_id="i1", surface="detail", payload={"ratio": 0.0}),
        ]
    return poison


@pytest.mark.parametrize("name", sorted(SIGNAL_REGISTRY.keys()))
def test_signal_is_blind_to_events_at_or_after_its_seal(name):
    fn = SIGNAL_REGISTRY[name]
    baseline = _baseline_events()
    poisoned = baseline + _poison_events(WINDOW.t_end)

    baseline_value = fn(baseline, WINDOW, CTX)
    poisoned_value = fn(poisoned, WINDOW, CTX)

    assert poisoned_value == baseline_value, (
        f"{name} changed when poison events at/after the seal were added "
        f"({baseline_value!r} -> {poisoned_value!r}) — it read past its window."
    )


@pytest.mark.parametrize("name", sorted(SIGNAL_REGISTRY.keys()))
def test_signal_produces_a_legitimate_value_on_the_baseline(name):
    """Guards against a vacuous pass above: if a signal always returns
    None regardless of input, the leakage test can't tell "blind to
    poison" apart from "blind to everything." Every Gate 0 signal must
    produce a real value on a reasonable baseline."""
    fn = SIGNAL_REGISTRY[name]
    value = fn(_baseline_events(), WINDOW, CTX)
    assert value is not None, f"{name} returned None on a baseline built to exercise it"


def test_events_in_window_excludes_event_exactly_at_seal():
    events = [RawEvent(t=2000.0, type="pointer_sample", item_id="i1", surface="detail", payload={"x": 0, "y": 0})]
    assert events_in_window(events, WINDOW) == []


def test_events_in_window_includes_event_just_before_seal():
    events = [RawEvent(t=1999.999, type="pointer_sample", item_id="i1", surface="detail", payload={"x": 0, "y": 0})]
    assert events_in_window(events, WINDOW) == events


def test_zero_length_window_every_signal_returns_none():
    """A commitment landing inside the 1000ms buffer collapses the window
    to zero length (see seal_window_for_view) — every signal must degrade
    to None here, never crash and never impute a value."""
    zero_window = WindowSpec(t_start=500.0, t_end=500.0, seal_reason="commitment_seal")
    baseline = _baseline_events()
    for name, fn in SIGNAL_REGISTRY.items():
        assert fn(baseline, zero_window, CTX) is None, f"{name} did not degrade to None on a zero-length window"


def test_touch_pointer_type_disables_the_whole_motor_family():
    touch_ctx = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="touch")
    baseline = _baseline_events()
    motor_signals = [
        "hover_dwell_on_target",
        "peak_pointer_velocity_on_approach",
        "trajectory_curvature_auc",
        "trajectory_x_flips",
    ]
    for name in motor_signals:
        assert SIGNAL_REGISTRY[name](baseline, WINDOW, touch_ctx) is None, f"{name} should be gated off for touch"
