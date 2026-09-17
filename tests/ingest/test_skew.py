"""§10.9 skew test: "replay a logged session offline at the same sealed
checkpoints the online path used; compare with per-feature tolerances...
Log a continuous skew metric per deploy rather than asserting a boolean."

The "online path" here is the mode the SDK attaches to each `view_start`/
`detail_view_start` envelope in real time (sdk/src/mode.ts). The "offline
path" is server/features/replay.py recomputing mode from the same raw
stored log via server/features/mode.py. This test drives a real browser
session's worth of synthetic events through both computations and reports
agreement — it's a fixture-built stand-in for "replay a logged session"
since there's no deployed traffic yet to replay for real; STATE.md flags
that a live-traffic version of this test is a follow-up once the site is
deployed and has real sessions to pull from.
"""
import uuid

from server.features.replay import recompute_session


def _envelope(t, seq, item_id, surface, mode, event_type, session_id, payload_extra=None):
    payload = dict(payload_extra or {})
    if item_id:
        payload["item_id"] = item_id
    return {
        "event_id": str(uuid.uuid4()),
        "seq": seq,
        "ts_mono": t,
        "ts_wall": "2026-01-01T00:00:00Z",
        "demo": False,
        "surface": surface,
        "mode": mode,
        "type": event_type,
        "payload": payload,
    }


def _scripted_session(session_id: str) -> tuple[list[dict], dict[str, str]]:
    """A hand-scripted session exercising all five modes, with the "online"
    mode baked into each event exactly as sdk/src/mode.ts's rules would
    compute it in real time — i.e. this *is* the online path's output,
    captured as fixture data instead of driven through a real browser.

    Item-C's view is preceded by a `page_view` on the `category` surface,
    standing in for a real category-nav-link click — that's the one thing
    the online SDK tracks (`recordCategoryNavClick`) that has no
    persisted event type of its own (§7.2 has no slot for it), so
    replay.py proxies it with exactly this signal. Modeling the fixture
    around that proxy rather than around some other, unobservable signal
    keeps this a fair test of the *documented* simplification instead of
    an unrelated one.
    """
    events = [
        _envelope(0, 0, None, "home", None, "page_view", session_id),
        # discovery: no query, arriving via category grid
        _envelope(100, 1, "item-A", "category", "discovery", "view_start", session_id),
        _envelope(500, 2, "item-A", "category", None, "view_end", session_id),
        # directed_search: 3+ token query active
        _envelope(1000, 3, None, "search", None, "search", session_id, {"query": "blue running shoes"}),
        _envelope(1100, 4, "item-B", "search", "directed_search", "view_start", session_id),
        _envelope(1500, 5, "item-B", "search", None, "view_end", session_id),
        # a category nav click (=> a fresh category page_view) expires the search
        _envelope(1800, 6, None, "category", None, "page_view", session_id),
        # comparison: item-C and item-D share a near-substitute set, within 120s
        _envelope(2000, 7, "item-C", "category", "discovery", "view_start", session_id),
        _envelope(2400, 8, "item-C", "category", None, "view_end", session_id),
        _envelope(2500, 9, "item-D", "category", "comparison", "view_start", session_id),
        _envelope(2900, 10, "item-D", "category", None, "view_end", session_id),
        # refind: item-A viewed again, >=60s after its first view (t=100)
        _envelope(65_000, 11, "item-A", "category", "refind", "view_start", session_id),
        _envelope(65_400, 12, "item-A", "category", None, "view_end", session_id),
    ]
    near_substitute_set_by_item = {"item-C": "set-1", "item-D": "set-1"}
    return events, near_substitute_set_by_item


def test_online_and_offline_modes_agree_on_a_scripted_session():
    session_id = str(uuid.uuid4())
    events, near_substitute_set_by_item = _scripted_session(session_id)

    online_by_view = {
        (e["payload"]["item_id"], e["ts_mono"]): e["mode"]
        for e in events
        if e["type"] in ("view_start", "detail_view_start")
    }

    offline_views = recompute_session(events, near_substitute_set_by_item, brand_tokens=set())

    assert len(offline_views) == len(online_by_view), (
        f"offline recomputed {len(offline_views)} views, online recorded {len(online_by_view)} — "
        "a view count mismatch means the skew metric below can't even compare like-for-like."
    )

    mismatches = []
    for v in offline_views:
        key = (v.item_id, v.start)
        online_mode = online_by_view.get(key)
        if online_mode != v.mode:
            mismatches.append((key, online_mode, v.mode))

    skew_rate = len(mismatches) / len(offline_views)
    # Logged as a continuous metric, per §10.9, not just asserted as a
    # boolean — a future CI run can track this number over time.
    print(f"mode skew rate: {skew_rate:.4f} ({len(mismatches)}/{len(offline_views)} views)")
    assert skew_rate == 0.0, f"online/offline mode mismatches: {mismatches}"
