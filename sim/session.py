"""Simulates one browsing session for one archetype against the real
catalog, producing a raw event stream in the exact shape
server/features/window_spec.RawEvent expects — the simulator's output
feeds the same item_view.py / signals.py pipeline real telemetry does,
so there is exactly one code path from events to features, never a
simulator-only shortcut.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from sim.agents import Archetype, utility
from sim.embedding import ItemVector
from sim.generative import dwell_via_drift_diffusion, fixation_jitter, reach_trajectory, reading_scroll
from server.features.item_view import MIN_QUALIFYING_DURATION_MS
from server.features.window_spec import CommitmentEvent, RawEvent

GRID_COLS = 4
CELL_W, CELL_H = 320.0, 340.0
GRID_ORIGIN = (80.0, 200.0)

# NOT the fast-skip *label* threshold (server/features/labels.py's
# FAST_SKIP_THRESHOLD_MS_DEFAULT, 1500ms, a much later and separate
# concern) — this is item_view.py's own 300ms qualifying-exposure floor:
# below it, no canonical view opens *at all*, so there's nothing for the
# label logic to even look at. Imported rather than duplicated so the two
# modules can't silently drift apart.


@dataclass
class SimulatedView:
    item_id: str
    utility: float
    dwell_ms: float
    committed: bool
    start: float
    end: float


@dataclass
class SimulatedSession:
    session_id: str
    archetype_name: str
    events: list[RawEvent]
    commitment_events: list[CommitmentEvent]
    views: list[SimulatedView]


def _grid_position(index: int) -> tuple[float, float]:
    col = index % GRID_COLS
    row = index // GRID_COLS
    x, y = GRID_ORIGIN
    return (x + col * CELL_W + CELL_W / 2, y + row * CELL_H + CELL_H / 2)


def simulate_session(
    session_id: str,
    archetype: Archetype,
    item_pool: list[ItemVector],
    n_items: int,
    rng: random.Random,
    surface: str = "category",
) -> SimulatedSession:
    """Browses `n_items` from `item_pool` in the order given (the caller
    decides ranking/shuffling — this function is agnostic to it, so it
    can be fed a real order or a shuffled one for the negative control)."""
    events: list[RawEvent] = []
    commitments: list[CommitmentEvent] = []
    views: list[SimulatedView] = []

    t = 0.0
    cursor = (400.0, 100.0)

    for i, item in enumerate(item_pool[:n_items]):
        u = utility(archetype, item.vector)
        result = dwell_via_drift_diffusion(u, archetype, rng)

        target = _grid_position(i)
        reach = reach_trajectory(cursor, target, archetype, rng, t0=t)
        for p in reach:
            events.append(RawEvent(t=p.t, type="pointer_sample", item_id=item.item_id, surface=surface, payload={"x": p.x, "y": p.y}))
        t_reach_end = reach[-1].t if reach else t
        cursor = (reach[-1].x, reach[-1].y) if reach else cursor

        remaining_dwell = max(0.0, result.dwell_ms - (t_reach_end - t))
        if remaining_dwell > 0:
            jitter = fixation_jitter(target, remaining_dwell, archetype, rng, t0=t_reach_end)
            for p in jitter:
                events.append(RawEvent(t=p.t, type="pointer_sample", item_id=item.item_id, surface=surface, payload={"x": p.x, "y": p.y}))

        scroll = reading_scroll(result.dwell_ms, archetype, rng, t0=t, start_ratio=min(1.0, i / max(1, n_items)))
        for s in scroll:
            events.append(RawEvent(t=s.t, type="scroll_sample", item_id=None, surface=surface, payload={"y_ratio": s.y_ratio}))

        view_start_t = t
        view_end_t = t + result.dwell_ms
        if result.dwell_ms >= MIN_QUALIFYING_DURATION_MS:
            events.append(RawEvent(t=view_start_t, type="visibility_sample", item_id=item.item_id, surface=surface, payload={"ratio": 1.0}))
            events.append(RawEvent(t=view_end_t, type="visibility_sample", item_id=item.item_id, surface=surface, payload={"ratio": 0.0}))
            views.append(
                SimulatedView(
                    item_id=item.item_id, utility=u, dwell_ms=result.dwell_ms, committed=result.committed_positive,
                    start=view_start_t, end=view_end_t,
                )
            )
            if result.committed_positive:
                commit_t = view_end_t + 200.0
                commitments.append(CommitmentEvent(t=commit_t, item_id=item.item_id, type="cart_add"))
                events.append(RawEvent(t=commit_t, type="cart_add", item_id=item.item_id, surface=surface, payload={"item_id": item.item_id, "quantity": 1}))

        t = view_end_t + rng.uniform(50, 200)  # brief transition before the next item

    return SimulatedSession(
        session_id=session_id, archetype_name=archetype.name, events=events, commitment_events=commitments, views=views,
    )
