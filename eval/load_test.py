"""§12's load test: "p95 < 250ms from trigger to pushed update... on
semantic triggers (view end, hover threshold, scroll milestone, panel
open, search submit), not on every flush."

The running system unifies those triggers into one condition
(server/ingest/live_scoring.py: a batch that causes at least one
canonical view to *close*), whichever event shape produced the close --
so this measures exactly that: for each WebSocket batch that closes a
view, the wall-clock time from sending the batch to receiving the
resulting `profile_update` message on the same connection. Batches that
do not close a view never get scored or pushed (score_session_update
returns None, and routes.py correctly skips the send) and are never
counted here, matching "not on every flush."

Run against the live dev stack (`uvicorn server.main:app --port 8090`,
Postgres + Redis up, ranker artifacts already trained) -- NOT against
the simulator, and not against a deployed URL: a local run measures the
application's own latency, which is what this budget is about, without
conflating in network latency to a hosted region.

Usage:
    python -m eval.load_test [--sessions 20] [--views-per-session 5] [--host ws://localhost:8090]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import uuid
from dataclasses import dataclass, field

import websockets

from server.catalog_store import get_store


@dataclass
class SessionResult:
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _envelope(session_id: str, seq: int, ts_mono: float, surface: str, type_: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id,
        "seq": seq,
        "ts_mono": ts_mono,
        "ts_wall": time.time() * 1000,
        "demo": False,
        "surface": surface,
        "type": type_,
        "payload": payload,
    }


async def _run_session(host: str, item_ids: list[str], views: int, timeout_s: float) -> SessionResult:
    session_id = str(uuid.uuid4())
    code = f"load-{session_id[:8]}"
    result = SessionResult()
    seq = 0
    t_mono = 0.0

    uri = f"{host}/ws?session_id={session_id}&code={code}"
    async with websockets.connect(uri) as ws:
        # Establish the session with a page_view carrying device info, as
        # a real browser session always does first (server/ingest/routes.py's
        # _capture_device_info) -- not itself a scored trigger.
        seq += 1
        t_mono += 50
        await ws.send(json.dumps([
            _envelope(session_id, seq, t_mono, "home", "page_view",
                      {"path": "/", "device": {"browser": "LoadTest", "pointer_type": "mouse", "engine_version": "0.0.0"}}),
        ]))

        for i in range(views):
            item_id = item_ids[i % len(item_ids)]
            seq += 1
            start_t = t_mono + 100
            seq2 = seq + 1
            end_t = start_t + 2000  # a 2s dwell on the simulated timeline, well past the 300ms canonical-view floor
            batch = [
                _envelope(session_id, seq, start_t, "detail", "view_start", {"item_id": item_id}),
                _envelope(session_id, seq2, end_t, "detail", "view_end", {"item_id": item_id}),
            ]
            seq = seq2
            t_mono = end_t

            t0 = time.perf_counter()
            await ws.send(json.dumps(batch))
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                    msg = json.loads(raw)
                    if msg.get("type") == "profile_update":
                        t1 = time.perf_counter()
                        result.latencies_ms.append((t1 - t0) * 1000)
                        break
            except asyncio.TimeoutError:
                result.errors.append(f"view {i}: no profile_update within {timeout_s}s")

    return result


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", type=int, default=20, help="concurrent simulated sessions")
    parser.add_argument("--views-per-session", type=int, default=5, help="scored (view_start+view_end) triggers per session")
    parser.add_argument("--host", type=str, default="ws://localhost:8090", help="backend WS origin (not the Vite proxy)")
    parser.add_argument("--timeout", type=float, default=5.0, help="seconds to wait for a push before counting it as missing")
    args = parser.parse_args()

    store = get_store()
    item_ids = [i["item_id"] for i in store.all_items[:50]]
    if not item_ids:
        raise SystemExit("catalog is empty -- run `python -m catalog.build` first")

    print(f"Running {args.sessions} concurrent sessions x {args.views_per_session} triggers against {args.host} ...")
    t_start = time.perf_counter()
    results = await asyncio.gather(*[
        _run_session(args.host, item_ids, args.views_per_session, args.timeout)
        for _ in range(args.sessions)
    ])
    wall_s = time.perf_counter() - t_start

    all_latencies = [lat for r in results for lat in r.latencies_ms]
    all_errors = [e for r in results for e in r.errors]
    expected = args.sessions * args.views_per_session

    print()
    print(f"Triggers expected:  {expected}")
    print(f"Triggers measured:  {len(all_latencies)}")
    print(f"Missing/timed out:  {len(all_errors)}")
    for e in all_errors[:10]:
        print(f"  - {e}")
    print(f"Wall clock:         {wall_s:.2f}s")
    print()
    if all_latencies:
        print(f"p50 latency:  {_percentile(all_latencies, 0.50):.1f}ms")
        print(f"p90 latency:  {_percentile(all_latencies, 0.90):.1f}ms")
        print(f"p95 latency:  {_percentile(all_latencies, 0.95):.1f}ms")
        print(f"p99 latency:  {_percentile(all_latencies, 0.99):.1f}ms")
        print(f"max latency:  {max(all_latencies):.1f}ms")
        print()
        p95 = _percentile(all_latencies, 0.95)
        budget = 250.0
        verdict = "PASS" if p95 < budget else "FAIL"
        print(f"Section 12 budget: p95 < {budget}ms -> {verdict} ({p95:.1f}ms)")
    else:
        print("No triggers produced a measurement -- nothing to report.")


if __name__ == "__main__":
    asyncio.run(main())
