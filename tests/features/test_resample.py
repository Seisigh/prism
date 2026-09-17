"""§15 test 8: one trajectory sampled at different rates yields features
within tolerance, after resampling onto the common 60Hz grid."""
import math

from server.features.resample import resample_pointer_trajectory
from server.features.signals import ItemContext, trajectory_curvature_auc
from server.features.window_spec import RawEvent, WindowSpec

CTX = ItemContext(item_id="i1", surface="detail", mode="discovery", pointer_type="mouse")


def _underlying_path(t: float) -> tuple[float, float]:
    # A smooth curve: a gentle arc from (0,0) to (200,100) over 1000ms.
    frac = t / 1000.0
    return (200 * frac, 100 * math.sin(frac * math.pi))


def _sample_at(times: list[float]) -> list[RawEvent]:
    return [
        RawEvent(t=t, type="pointer_sample", item_id="i1", surface="detail", payload={"x": x, "y": y})
        for t in times
        for x, y in [_underlying_path(t)]
    ]


def test_resampling_makes_different_native_rates_agree_within_tolerance():
    # A "fast" browser sampling every 8ms (~120Hz) vs a "slow" one every
    # 33ms (~30Hz) of the exact same underlying motion.
    fast_native = _sample_at([i * 8.0 for i in range(126)])   # 0..1000ms
    slow_native = _sample_at([i * 33.0 for i in range(31)])   # 0..~1000ms

    fast_resampled = resample_pointer_trajectory(fast_native, "i1", "detail")
    slow_resampled = resample_pointer_trajectory(slow_native, "i1", "detail")

    window = WindowSpec(t_start=0, t_end=1001, seal_reason="view_close")
    fast_curvature = trajectory_curvature_auc(fast_resampled, window, CTX)
    slow_curvature = trajectory_curvature_auc(slow_resampled, window, CTX)

    assert fast_curvature is not None and slow_curvature is not None
    # Same underlying motion, two different native sample rates: within
    # 5% of each other post-resampling.
    assert abs(fast_curvature - slow_curvature) / fast_curvature < 0.05


def test_resampling_output_lands_on_the_60hz_grid():
    native = _sample_at([0.0, 250.0, 500.0, 750.0, 1000.0])
    resampled = resample_pointer_trajectory(native, "i1", "detail")
    diffs = [b.t - a.t for a, b in zip(resampled, resampled[1:])]
    assert all(abs(d - (1000.0 / 60)) < 1e-6 for d in diffs)
