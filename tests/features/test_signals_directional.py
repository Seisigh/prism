"""server/features/signals_directional.py: the two signals added after
diagnosing that the existing eighteen signals all measure magnitude/shape
of motion and none of them measure *which* target a trajectory leaned
toward. Covers the tautology guard (early window + seal exclusion, not
final position), the scale-free ratio, and the diagnostic-only function's
exclusion from the real registry.
"""
from server.features.signals import ItemContext
from server.features.signals_directional import (
    DIRECTIONAL_SIGNAL_REGISTRY,
    _full_trajectory_direction_bias_DIAGNOSTIC_ONLY,
    direction_stabilization_fraction,
    early_direction_bias,
)
from server.features.window_spec import RawEvent, WindowSpec

ACCEPT_POS = (100.0, 0.0)
REJECT_POS = (-100.0, 0.0)


def _ctx(**overrides) -> ItemContext:
    base = dict(item_id="i1", surface="category", mode="discovery", pointer_type="mouse", accept_pos=ACCEPT_POS, reject_pos=REJECT_POS)
    base.update(overrides)
    return ItemContext(**base)


def _pointer(t: float, x: float, y: float = 0.0) -> RawEvent:
    return RawEvent(t=t, type="pointer_sample", item_id="i1", surface="category", payload={"x": x, "y": y})


def test_early_direction_bias_positive_when_leaning_accept():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")  # early window = [0, 2000)
    events = [_pointer(t, x=90.0) for t in (0.0, 500.0, 1000.0, 1500.0)]
    value = early_direction_bias(events, window, _ctx())
    assert value is not None and value > 0.5


def test_early_direction_bias_negative_when_leaning_reject():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [_pointer(t, x=-90.0) for t in (0.0, 500.0, 1000.0, 1500.0)]
    value = early_direction_bias(events, window, _ctx())
    assert value is not None and value < -0.5


def test_early_direction_bias_bounded_to_unit_interval():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [_pointer(t, x=100.0) for t in (0.0, 500.0, 1000.0)]  # sitting exactly on accept_pos
    value = early_direction_bias(events, window, _ctx())
    assert value is not None and -1.0 <= value <= 1.0


def test_early_direction_bias_ignores_samples_outside_the_narrower_of_the_two_windows():
    """duration=1200ms: first-third would allow up to 400ms, but the
    seal exclusion (duration - 1000ms = 200ms) binds tighter -- only
    samples before t=200 should count."""
    window = WindowSpec(t_start=0.0, t_end=1200.0, seal_reason="view_close")
    counted = _pointer(t=100.0, x=95.0)  # inside [0, 200) -> leans accept
    excluded = _pointer(t=300.0, x=-95.0)  # inside [200, 400) -> would count under first-third alone, but not under the tighter exclusion-floor window
    value = early_direction_bias([counted, excluded], window, _ctx())
    assert value is not None and value > 0.5


def test_early_direction_bias_none_for_short_views_with_no_valid_early_window():
    """duration=900ms: first-third=300ms, exclusion floor = 900-1000 = -100
    -> no valid early window at all. This is the real, correctly-reported
    unavailability case for the fastest, most confident decisions."""
    window = WindowSpec(t_start=0.0, t_end=900.0, seal_reason="view_close")
    events = [_pointer(t=100.0, x=95.0)]
    assert early_direction_bias(events, window, _ctx()) is None


def test_early_direction_bias_none_for_touch():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [_pointer(t, x=90.0) for t in (0.0, 500.0)]
    assert early_direction_bias(events, window, _ctx(pointer_type="touch")) is None


def test_early_direction_bias_none_without_a_reject_position():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [_pointer(t, x=90.0) for t in (0.0, 500.0)]
    assert early_direction_bias(events, window, _ctx(reject_pos=None)) is None


def test_early_direction_bias_blind_to_events_at_or_after_the_view_seal():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    baseline = [_pointer(t, x=90.0) for t in (0.0, 500.0, 1000.0)]
    poisoned = baseline + [_pointer(6000.0, x=-999999.0), _pointer(11000.0, x=-999999.0)]
    baseline_value = early_direction_bias(baseline, window, _ctx())
    poisoned_value = early_direction_bias(poisoned, window, _ctx())
    assert baseline_value == poisoned_value


def test_direction_stabilization_fraction_finds_the_last_sign_change():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")  # pre-exclusion window = [0, 5000)
    events = [
        _pointer(0.0, x=-90.0),
        _pointer(1000.0, x=-90.0),
        _pointer(2000.0, x=90.0),
        _pointer(3000.0, x=90.0),
        _pointer(4000.0, x=90.0),
    ]
    value = direction_stabilization_fraction(events, window, _ctx())
    assert value == 2000.0 / 6000.0


def test_direction_stabilization_fraction_ignores_the_final_1000ms():
    """A sign flip inside the excluded final 1000ms must not move the
    reported lock time -- only the pre-exclusion window is scanned."""
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [
        _pointer(0.0, x=-90.0),
        _pointer(2000.0, x=90.0),
        _pointer(3000.0, x=90.0),
        _pointer(5500.0, x=-90.0),  # inside [5000, 6000) -- excluded
    ]
    value = direction_stabilization_fraction(events, window, _ctx())
    assert value == 2000.0 / 6000.0


def test_direction_stabilization_fraction_none_for_touch():
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = [_pointer(0.0, x=90.0)]
    assert direction_stabilization_fraction(events, window, _ctx(pointer_type="touch")) is None


def test_diagnostic_only_function_is_not_in_the_real_registry():
    assert "_full_trajectory_direction_bias_DIAGNOSTIC_ONLY" not in DIRECTIONAL_SIGNAL_REGISTRY
    assert set(DIRECTIONAL_SIGNAL_REGISTRY.keys()) == {"early_direction_bias", "direction_stabilization_fraction"}


def test_diagnostic_only_function_sees_the_final_position_unlike_the_real_signal():
    """Demonstrates the tautology the real signal avoids: a trajectory
    that spends its early life leaning reject but ends up sitting right
    on accept_pos (as it would right before a cart add) reads *negative*
    on the real, early-only signal but *positive* on the full-trajectory
    diagnostic -- because the diagnostic is dominated by the many samples
    resting on the final position."""
    window = WindowSpec(t_start=0.0, t_end=6000.0, seal_reason="view_close")
    events = (
        [_pointer(t, x=-90.0) for t in (0.0, 500.0, 1000.0, 1500.0)]
        + [_pointer(t, x=99.0) for t in (2500.0, 3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 5999.0)]
    )
    early_value = early_direction_bias(events, window, _ctx())
    full_value = _full_trajectory_direction_bias_DIAGNOSTIC_ONLY(events, window, _ctx())
    assert early_value is not None and early_value < 0
    assert full_value is not None and full_value > 0
