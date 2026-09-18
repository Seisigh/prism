"""server/features/live.py: real-event feature extraction, the
real-telemetry counterpart to eval/features.py."""
from server.features.live import LiveView, extract_session_features, view_is_fast_skip
from server.features.window_spec import CommitmentEvent


def _row(t, type_, surface="detail", payload=None):
    return {"ts_mono": t, "type": type_, "surface": surface, "payload": payload or {}}


def _pointer_rows(item_id, times_and_xy, surface="detail"):
    return [_row(t, "pointer_sample", surface, {"item_id": item_id, "x": x, "y": y}) for t, x, y in times_and_xy]


def test_extract_session_features_returns_one_row_per_view_with_all_signal_names():
    events = _pointer_rows("i1", [(0, 0, 0), (200, 40, 20), (400, 80, 40)])
    views = [LiveView(item_id="i1", surface="detail", mode="discovery", start=0.0, end=2000.0, category="Kitchen & Dining", near_substitute_set_id=None)]
    result = extract_session_features(events, views)
    assert len(result) == 1
    from server.features.live import ALL_SIGNALS

    assert set(result[0].keys()) == set(ALL_SIGNALS.keys())


def test_directional_signals_are_always_none_for_real_sessions():
    """No accept_pos/reject_pos exists in real telemetry today -- both
    directional signals must degrade to None, never a synthesized value."""
    events = _pointer_rows("i1", [(0, 0, 0), (200, 40, 20), (400, 80, 40)])
    views = [LiveView(item_id="i1", surface="detail", mode="discovery", start=0.0, end=6000.0, category="Kitchen & Dining", near_substitute_set_id=None)]
    result = extract_session_features(events, views)
    assert result[0]["early_direction_bias"] is None
    assert result[0]["direction_lock_in_speed"] is None


def test_revisit_count_reflects_earlier_views_of_the_same_item():
    """extract_session_features returns *normalized* (z-scored) values,
    so the raw revisit_count (0 for the first view, 1 for the second)
    isn't recoverable exactly -- only the ordering is asserted."""
    events = _pointer_rows("i1", [(0, 0, 0)]) + _pointer_rows("i1", [(5000, 0, 0)])
    views = [
        LiveView(item_id="i1", surface="detail", mode="discovery", start=0.0, end=2000.0, category="c", near_substitute_set_id=None),
        LiveView(item_id="i1", surface="detail", mode="discovery", start=5000.0, end=7000.0, category="c", near_substitute_set_id=None),
    ]
    result = extract_session_features(events, views)
    assert result[0]["revisit_count"] < result[1]["revisit_count"]


def test_view_is_fast_skip_true_for_a_short_unrevisited_uncommitted_view():
    view = LiveView(item_id="i1", surface="detail", mode="discovery", start=0.0, end=500.0, category="c", near_substitute_set_id=None)
    assert view_is_fast_skip(view, [view], commitment_events=[]) is True


def test_view_is_fast_skip_false_when_later_committed():
    view = LiveView(item_id="i1", surface="detail", mode="discovery", start=0.0, end=500.0, category="c", near_substitute_set_id=None)
    commitment = CommitmentEvent(t=600.0, item_id="i1", type="cart_add")
    assert view_is_fast_skip(view, [view], commitment_events=[commitment]) is False
