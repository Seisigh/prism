"""server/features/composites.py: the declared, fixed signal->family
mapping (§11's five composites) and the availability meta-signal."""
from server.features.composites import FAMILIES, compute_composites


def _all_present(value: float = 1.0) -> dict[str, float | None]:
    return {
        "item_dwell": value, "viewport_time": value, "hover_dwell_on_target": value, "focused_idle": value,
        "peak_pointer_velocity_on_approach": value, "trajectory_curvature_auc": value, "trajectory_x_flips": value,
        "acceleration_profile": value, "pause_count": value,
        "max_scroll_depth": value, "scroll_reversals": value, "category_breadth": value, "query_specificity": value,
        "revisit_count": value, "near_substitute_coview_count": value,
    }


def test_all_five_families_present_in_output():
    result = compute_composites(_all_present())
    assert set(result.keys()) == set(FAMILIES)


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
    signals["item_dwell"] = 1.0  # 1 of 15 behavioral signals present
    result = compute_composites(signals)
    assert result["availability"].value == 1 / 15


def test_availability_composite_never_none():
    signals = {name: None for name in _all_present()}
    result = compute_composites(signals)
    assert result["availability"].value == 0.0
