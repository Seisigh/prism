"""server/features/composites.py: the declared, fixed signal->family
mapping (§11's five composites, plus the `directional` family added
after Gate 1's ranker recovery stalled -- see STATE.md) and the
availability meta-signal."""
import inspect

from server.features import composites as composites_module
from server.features.composites import FAMILIES, compute_composites


def _all_present(value: float = 1.0) -> dict[str, float | None]:
    return {
        "item_dwell": value, "viewport_time": value, "hover_dwell_on_target": value, "focused_idle": value,
        "peak_pointer_velocity_on_approach": value, "trajectory_curvature_auc": value, "trajectory_x_flips": value,
        "acceleration_profile": value, "pause_count": value,
        "max_scroll_depth": value, "scroll_reversals": value, "category_breadth": value, "query_specificity": value,
        "revisit_count": value, "near_substitute_coview_count": value,
        "early_direction_bias": value, "direction_lock_in_speed": value,
    }


def test_all_families_present_in_output():
    result = compute_composites(_all_present())
    assert set(result.keys()) == set(FAMILIES)
    assert "directional" in result


def test_composite_is_none_when_every_constituent_is_none():
    signals = {name: None for name in _all_present()}
    result = compute_composites(signals)
    assert result["attention"].value is None
    assert result["attention"].availability == 0.0


def test_composite_averages_only_available_constituents():
    signals = _all_present(value=None)
    signals["item_dwell"] = 2.0
    signals["viewport_time"] = 4.0
    # hover_dwell_on_target, focused_idle stay None.
    result = compute_composites(signals)
    assert result["attention"].value == 3.0
    assert result["attention"].availability == 0.5


def test_query_specificity_is_sign_flipped_in_exploration():
    baseline = _all_present(value=0.0)
    result_baseline = compute_composites(baseline)

    specific_query = dict(baseline)
    specific_query["query_specificity"] = 2.0
    result_specific = compute_composites(specific_query)

    assert result_specific["exploration"].value < result_baseline["exploration"].value


def test_availability_composite_reflects_fraction_of_behavioral_signals_present():
    signals = _all_present(value=None)
    total_behavioral = len(_all_present())
    signals["item_dwell"] = 1.0  # 1 of N behavioral signals present
    result = compute_composites(signals)
    assert result["availability"].value == 1 / total_behavioral


def test_availability_composite_never_none():
    signals = {name: None for name in _all_present()}
    result = compute_composites(signals)
    assert result["availability"].value == 0.0


def test_directional_signal_sign_survives_into_the_composite():
    """The guard the author asked for: a signed directional signal must
    not have its sign discarded on the way into the composite. Positive
    early_direction_bias (leaning accept) must produce a positive
    `directional` composite; negative must produce negative."""
    leaning_accept = _all_present(value=None)
    leaning_accept["early_direction_bias"] = 0.8
    leaning_reject = _all_present(value=None)
    leaning_reject["early_direction_bias"] = -0.8

    assert compute_composites(leaning_accept)["directional"].value > 0
    assert compute_composites(leaning_reject)["directional"].value < 0


def test_composites_module_never_takes_an_absolute_value():
    """Static check that the actual composite-computation code (not the
    module's prose docstring, which discusses this rule by name) never
    applies abs() or math.fabs() -- the exact operation that would
    discard a directional signal's sign on its way into a composite.
    Guards against a future edit reintroducing it, the same way
    tests/sim/test_session.py statically checks mode is never assigned
    directly rather than trusting a docstring."""
    for fn in (composites_module.compute_composites, composites_module.availability_composite):
        source = inspect.getsource(fn)
        assert "abs(" not in source
        assert "fabs(" not in source
