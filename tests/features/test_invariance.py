"""§15 test 7: curvature rotation-invariant, normalizers scale-invariant,
dwell monotone in exposure."""
import math

from server.features.signals import ItemContext, item_dwell, trajectory_curvature_auc
from server.features.window_spec import RawEvent, WindowSpec

CTX = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")


def _rotate(x: float, y: float, theta: float, cx: float = 50.0, cy: float = 50.0) -> tuple[float, float]:
    dx, dy = x - cx, y - cy
    return (
        cx + dx * math.cos(theta) - dy * math.sin(theta),
        cy + dx * math.sin(theta) + dy * math.cos(theta),
    )


def _path_events(points: list[tuple[float, float, float]]) -> list[RawEvent]:
    return [
        RawEvent(t=t, type="pointer_sample", item_id="i1", surface="detail", payload={"x": x, "y": y})
        for t, x, y in points
    ]


def test_curvature_is_rotation_invariant():
    raw_points = [(0, 0, 0), (250, 30, 60), (500, 60, 10), (750, 90, 70), (1000, 120, 20)]
    window = WindowSpec(t_start=0, t_end=1001, seal_reason="view_close")

    original = trajectory_curvature_auc(_path_events(raw_points), window, CTX)

    rotated_points = [(t, *_rotate(x, y, math.radians(37))) for t, x, y in raw_points]
    rotated = trajectory_curvature_auc(_path_events(rotated_points), window, CTX)

    assert original is not None and rotated is not None
    assert math.isclose(original, rotated, rel_tol=1e-9, abs_tol=1e-6)


def test_dwell_is_monotone_in_exposure_duration():
    window_short = WindowSpec(t_start=0, t_end=1000, seal_reason="view_close")
    window_medium = WindowSpec(t_start=0, t_end=5000, seal_reason="view_close")
    window_long = WindowSpec(t_start=0, t_end=30000, seal_reason="view_close")

    short = item_dwell([], window_short, CTX)
    medium = item_dwell([], window_medium, CTX)
    long_ = item_dwell([], window_long, CTX)

    assert short is not None and medium is not None and long_ is not None
    assert short < medium < long_


def test_z_score_is_scale_invariant():
    from server.features.normalize import z_score

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    x = 4.0
    baseline = z_score(x, values)

    scaled_values = [v * 100.0 for v in values]
    scaled_x = x * 100.0
    scaled = z_score(scaled_x, scaled_values)

    assert baseline is not None and scaled is not None
    assert math.isclose(baseline, scaled, rel_tol=1e-9)
