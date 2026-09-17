"""The six required item-view fixtures from BUILD_BRIEF.md §8. Hand-built
visibility timelines, not real telemetry — this is the load-bearing test
suite for the single most important function in the project.
"""
from server.features.item_view import (
    HardClose,
    PointerFocusSample,
    VisibilitySample,
    compute_item_views,
)


def vis(t, item_id, surface, ratio):
    return VisibilitySample(t=t, item_id=item_id, surface=surface, ratio=ratio)


# 1. Simple open/close ------------------------------------------------------


def test_simple_open_close():
    samples = [
        vis(0, "i1", "grid", 0.0),
        vis(0, "i1", "grid", 0.8),   # becomes visible
        vis(1000, "i1", "grid", 0.0),  # leaves
    ]
    views = compute_item_views(samples)
    assert len(views) == 1
    v = views[0]
    assert v.item_id == "i1"
    assert v.surface == "grid"
    assert v.start == 0
    assert v.end == 1000
    assert v.closed_by == "visibility_timeout"


def test_below_threshold_never_opens_a_view():
    samples = [vis(0, "i1", "grid", 0.3), vis(500, "i1", "grid", 0.4)]
    assert compute_item_views(samples) == []


def test_visible_but_under_300ms_does_not_qualify_alone():
    samples = [vis(0, "i1", "grid", 0.9), vis(200, "i1", "grid", 0.0)]
    assert compute_item_views(samples) == []


# 2. Merge-gap ---------------------------------------------------------------


def test_merge_gap_under_500ms_becomes_one_view():
    # Two 400ms qualifying runs separated by a 300ms dip (< 500ms) merge.
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(400, "i1", "grid", 0.0),   # dip starts
        vis(700, "i1", "grid", 0.9),   # dip ends (300ms gap)
        vis(1100, "i1", "grid", 0.0),  # leaves
    ]
    views = compute_item_views(samples)
    assert len(views) == 1
    assert views[0].start == 0
    assert views[0].end == 1100


def test_gap_at_or_above_500ms_does_not_merge():
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(400, "i1", "grid", 0.0),
        vis(1000, "i1", "grid", 0.9),  # 600ms gap: too long to merge
        vis(1400, "i1", "grid", 0.0),
    ]
    views = compute_item_views(samples)
    assert len(views) == 2
    assert (views[0].start, views[0].end) == (0, 400)
    assert (views[1].start, views[1].end) == (1000, 1400)


# 3. Multi-surface tie --------------------------------------------------------


def test_multi_surface_tie_resolves_to_pointer_focus():
    # Same item visible on "grid" and "detail" for an overlapping window;
    # pointer focus is on "detail" throughout -> detail wins entirely.
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(2000, "i1", "grid", 0.0),
        vis(0, "i1", "detail", 0.9),
        vis(2000, "i1", "detail", 0.0),
    ]
    focus = [PointerFocusSample(t=0, surface="detail")]
    views = compute_item_views(samples, pointer_focus_samples=focus)
    assert len(views) == 1
    assert views[0].surface == "detail"


def test_multi_surface_tie_resolves_to_deepest_surface_without_focus_signal():
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(2000, "i1", "grid", 0.0),
        vis(0, "i1", "compare", 0.9),
        vis(2000, "i1", "compare", 0.0),
    ]
    views = compute_item_views(samples)  # no pointer focus samples supplied
    assert len(views) == 1
    assert views[0].surface == "compare"  # compare (depth 1) beats grid (depth 0)


# 4. Tab blur mid-view --------------------------------------------------------


def test_tab_blur_force_closes_an_open_view():
    samples = [
        vis(0, "i1", "detail", 0.9),
        vis(5000, "i1", "detail", 0.0),  # would otherwise run to 5000
    ]
    closes = [HardClose(t=1500, kind="tab_blur")]
    views = compute_item_views(samples, hard_closes=closes)
    assert len(views) == 1
    assert views[0].end == 1500
    assert views[0].closed_by == "tab_blur"


def test_navigation_force_closes_an_open_view():
    samples = [vis(0, "i1", "grid", 0.9), vis(5000, "i1", "grid", 0.0)]
    closes = [HardClose(t=800, kind="navigation")]
    views = compute_item_views(samples, hard_closes=closes)
    assert views[0].end == 800
    assert views[0].closed_by == "navigation"


# 5. Rapid scroll producing sub-threshold exposures ---------------------------


def test_rapid_scroll_sub_threshold_blips_produce_no_view():
    # A sequence of <300ms blips with >500ms gaps between them: none
    # qualifies alone, and none is close enough to merge with another.
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(150, "i1", "grid", 0.0),
        vis(900, "i1", "grid", 0.9),
        vis(1050, "i1", "grid", 0.0),
        vis(1800, "i1", "grid", 0.9),
        vis(1950, "i1", "grid", 0.0),
    ]
    assert compute_item_views(samples) == []


def test_rapid_scroll_blip_between_two_qualifying_runs_is_absorbed():
    # A qualifying run, a sub-300ms blip, then another qualifying run. The
    # *total* elapsed gap between the two qualifying runs (350 -> 650,
    # i.e. 300ms) is under the 500ms merge threshold, so they merge into
    # one continuous view even though a non-qualifying blip sits inside
    # that gap — the blip must not fragment the view or count on its own.
    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(350, "i1", "grid", 0.0),   # first qualifying run: 350ms
        vis(450, "i1", "grid", 0.9),   # blip starts
        vis(550, "i1", "grid", 0.0),   # blip ends: 100ms, doesn't qualify alone
        vis(650, "i1", "grid", 0.9),   # second run starts (300ms total gap since 350)
        vis(1050, "i1", "grid", 0.0),  # second qualifying run: 400ms
    ]
    views = compute_item_views(samples)
    assert len(views) == 1
    assert views[0].start == 0
    assert views[0].end == 1050


# 6. Mode precedence: assigned once, at open, never mid-view -----------------


def test_mode_is_assigned_once_at_view_open():
    calls = []

    def resolver(item_id, surface, t):
        calls.append((item_id, surface, t))
        return "refind" if t == 0 else "discovery"

    samples = [
        vis(0, "i1", "grid", 0.9),
        vis(400, "i1", "grid", 0.0),
        vis(700, "i1", "grid", 0.9),  # merges via gap rule; view still opened at t=0
        vis(1200, "i1", "grid", 0.0),
    ]
    views = compute_item_views(samples, mode_resolver=resolver)
    assert len(views) == 1
    assert views[0].mode == "refind"
    # Resolver is called exactly once per emitted view, at its start time.
    assert calls == [("i1", "grid", 0)]
