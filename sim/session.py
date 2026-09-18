"""Simulates one browsing session for one archetype against the real
catalog, producing a raw event stream in the exact shape
server/features/window_spec.RawEvent expects — the simulator's output
feeds the same item_view.py / signals.py pipeline real telemetry does,
so there is exactly one code path from events to features, never a
simulator-only shortcut.

Mode is not sampled or assigned directly (per the author's explicit
instruction): it is an *observable consequence* of the agent's
session-level goal plus its own accumulating view history, computed by
running the exact same `server.features.mode.assign_mode` real ingested
sessions are scored with. A `SessionGoal` only ever supplies the
*fiction* of a search query (or nothing); everything else — refind from
revisiting, comparison from browsing a near-substitute set — falls out
of `assign_mode`'s own precedence rules applied to what the agent
actually did.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from sim.agents import Archetype, utility
from sim.embedding import ItemVector
from sim.generative import dwell_via_drift_diffusion, fixation_jitter, reach_trajectory, reading_scroll
from server.features.item_view import MIN_QUALIFYING_DURATION_MS
from server.features.mode import Mode, PriorView, QuerySubmission, assign_mode
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

# A goal-driven query's synthetic text — engineered to land on a specific
# side of server.features.mode.classify_query_tokens deterministically,
# not meant to resemble a real query a person would type. "acme" isn't a
# real invented catalog brand; it doesn't need to be, since directed
# classification here fires on the >=3-token rule regardless of whether
# "acme" is recognized as a brand token.
DIRECTED_QUERY_TEXT = "acme brand xz900"


@dataclass(frozen=True)
class SessionGoal:
    """A session-level goal the agent starts with. Exactly one of
    `target_item_id` / `target_category` may be set, or neither (a
    goalless, purely discovery-driven session)."""

    target_item_id: str | None = None
    target_category: str | None = None

    def __post_init__(self) -> None:
        if self.target_item_id is not None and self.target_category is not None:
            raise ValueError("SessionGoal takes at most one of target_item_id / target_category")

    @property
    def query_text(self) -> str | None:
        if self.target_item_id is not None:
            return DIRECTED_QUERY_TEXT
        if self.target_category is not None:
            # A single categorical token: not >=3 tokens, not model-token
            # shaped -> classify_query_tokens resolves this to "broad".
            return self.target_category.split()[0].lower()
        return None


@dataclass
class SimulatedView:
    item_id: str
    utility: float
    mode: Mode
    dwell_ms: float
    committed: bool
    start: float
    end: float
    # The two on-screen destinations the reach was blended between (see
    # generative.py) -- persisted here rather than recomputed downstream,
    # since a revisit reuses its item's *original* grid position and
    # re-deriving that in the feature layer would duplicate this
    # module's own browse-order bookkeeping.
    accept_pos: tuple[float, float] = (0.0, 0.0)
    reject_pos: tuple[float, float] = (0.0, 0.0)


@dataclass
class SimulatedSession:
    session_id: str
    archetype_name: str
    goal: SessionGoal
    events: list[RawEvent] = field(default_factory=list)
    commitment_events: list[CommitmentEvent] = field(default_factory=list)
    views: list[SimulatedView] = field(default_factory=list)


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
    goal: SessionGoal | None = None,
    revisit_prob: float = 0.15,
) -> SimulatedSession:
    """Browses up to `n_items` from `item_pool`, in order, with a chance
    at each step (`revisit_prob`) of instead going back to a previously
    viewed item — the only mechanism that can produce `refind` (nothing
    else in this function revisits an item), matching how a real refind
    happens: the visitor chooses to look again, it isn't scheduled.
    """
    goal = goal or SessionGoal()
    session = SimulatedSession(session_id=session_id, archetype_name=archetype.name, goal=goal)

    active_query = QuerySubmission(submitted_at=0.0, query=goal.query_text) if goal.query_text else None
    prior_views: list[PriorView] = []
    by_item_id = {iv.item_id: iv for iv in item_pool[:n_items]}
    browse_order = list(item_pool[:n_items])

    t = 0.0
    cursor = (400.0, 100.0)
    pool_index = 0

    for step in range(n_items):
        # Decide what gets viewed this step: a revisit, or the next new item.
        if prior_views and rng.random() < revisit_prob:
            revisit_target = rng.choice(prior_views)
            item = by_item_id[revisit_target.item_id]
            grid_index = next(i for i, v in enumerate(browse_order) if v.item_id == item.item_id)
        else:
            if pool_index >= len(browse_order):
                break
            item = browse_order[pool_index]
            grid_index = pool_index
            pool_index += 1

        mode = assign_mode(
            t=t,
            item_id=item.item_id,
            near_substitute_set_id=item.near_substitute_set_id,
            prior_views=prior_views,
            active_query=active_query,
            category_nav_click_at=None,
            brand_tokens=set(),
        )

        u = utility(archetype, item.vector)
        result = dwell_via_drift_diffusion(u, archetype, mode, rng)

        # accept_pos is the item's own card (staying on / committing to
        # it); reject_pos is the next item's position (moving on) — the
        # two on-screen destinations the DDM's evidence path blends
        # between as it evolves (see generative.py's module docstring).
        accept_pos = _grid_position(grid_index)
        reject_pos = _grid_position(grid_index + 1)
        reach = reach_trajectory(archetype, result.accumulator_path, cursor, accept_pos, reject_pos, rng, t0=t)
        for p in reach:
            session.events.append(RawEvent(t=p.t, type="pointer_sample", item_id=item.item_id, surface=surface, payload={"x": p.x, "y": p.y}))
        t_reach_end = reach[-1].t if reach else t
        cursor = (reach[-1].x, reach[-1].y) if reach else cursor

        diffusion_time = result.accumulator_path[-1].t if result.accumulator_path else 0.0
        fixation_duration = max(0.0, result.dwell_ms - diffusion_time)
        if fixation_duration > 0:
            jitter = fixation_jitter(archetype, result.accumulator_path, cursor, fixation_duration, rng, t0=t_reach_end)
            for p in jitter:
                session.events.append(RawEvent(t=p.t, type="pointer_sample", item_id=item.item_id, surface=surface, payload={"x": p.x, "y": p.y}))
            if jitter:
                cursor = (jitter[-1].x, jitter[-1].y)

        scroll = reading_scroll(archetype, result.accumulator_path, rng, t0=t, start_ratio=min(1.0, step / max(1, n_items)))
        for s in scroll:
            session.events.append(RawEvent(t=s.t, type="scroll_sample", item_id=None, surface=surface, payload={"y_ratio": s.y_ratio}))

        view_start_t = t
        view_end_t = t + result.dwell_ms
        if result.dwell_ms >= MIN_QUALIFYING_DURATION_MS:
            session.events.append(RawEvent(t=view_start_t, type="visibility_sample", item_id=item.item_id, surface=surface, payload={"ratio": 1.0}))
            session.events.append(RawEvent(t=view_end_t, type="visibility_sample", item_id=item.item_id, surface=surface, payload={"ratio": 0.0}))
            session.views.append(
                SimulatedView(
                    item_id=item.item_id, utility=u, mode=mode, dwell_ms=result.dwell_ms,
                    committed=result.committed_positive, start=view_start_t, end=view_end_t,
                    accept_pos=accept_pos, reject_pos=reject_pos,
                )
            )
            prior_views.append(PriorView(item_id=item.item_id, start=view_start_t, near_substitute_set_id=item.near_substitute_set_id))
            if result.committed_positive:
                commit_t = view_end_t + 200.0
                session.commitment_events.append(CommitmentEvent(t=commit_t, item_id=item.item_id, type="cart_add"))
                session.events.append(RawEvent(t=commit_t, type="cart_add", item_id=item.item_id, surface=surface, payload={"item_id": item.item_id, "quantity": 1}))

        t = view_end_t + rng.uniform(50, 200)  # brief transition before the next item

    return session
