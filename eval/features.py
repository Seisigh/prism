"""Turns a simulated session into per-view feature rows, running the
*real* sealed-window + signal + composite pipeline (server/features/)
against the simulator's output -- the same principle sim/session.py's
docstring states for events: one code path from raw behavior to
features, never a simulator-only shortcut.

Known simplification, flagged rather than assumed away: this reads view
boundaries and modes directly off `SimulatedSession.views` (already
computed by sim/session.py via the real `assign_mode`, honoring the same
300ms qualifying floor `item_view.py` enforces) rather than re-deriving
them from the raw event stream via `item_view.compute_item_views`. That
second pass would be pure duplication here since the two are
guaranteed consistent by construction (see sim/session.py's import of
MIN_QUALIFYING_DURATION_MS) -- but it does mean this module is not
exercising `item_view.py`'s own boundary-merging logic, only its
downstream consumers. The skew test (tests/ingest) is what actually
proves the online/offline view-boundary logic agree; this module only
needs the boundaries, not to re-prove them.

Touch is not modeled by the simulator yet (sim/generative.py has no
touch motor model) -- every row here has pointer_type="mouse". Flagged
in STATE.md: the motor-conflict family's recovery is therefore untested
for touch sessions.
"""
from __future__ import annotations

from dataclasses import dataclass

from server.features.composites import FAMILIES, compute_composites
from server.features.labels import is_fast_skip
from server.features.mode import COMPARISON_WINDOW_MS, QuerySubmission, is_query_active
from server.features.normalize import z_score
from server.features.signals import SIGNAL_REGISTRY, ItemContext
from server.features.signals_gate1 import GATE1_SIGNAL_REGISTRY
from server.features.window_spec import seal_window_for_view
from sim.embedding import ItemVector
from sim.session import SimulatedSession

ALL_SIGNALS = {**SIGNAL_REGISTRY, **GATE1_SIGNAL_REGISTRY}


@dataclass(frozen=True)
class ViewFeatureRow:
    session_id: str
    archetype_name: str
    item_id: str
    mode: str
    surface: str
    utility: float  # ground truth -- never a ranker input, only used for evaluation
    committed: bool
    is_fast_skip: bool
    composites: dict[str, float | None]  # family -> value
    availability: dict[str, float]  # family -> availability rate


def _active_query_token_count(session: SimulatedSession, t: float) -> int | None:
    goal_query = session.goal.query_text
    if goal_query is None:
        return None
    submission = QuerySubmission(submitted_at=0.0, query=goal_query)
    if not is_query_active(t, submission, category_nav_click_at=None):
        return None
    return len(goal_query.split())


def extract_session_features(
    session: SimulatedSession, item_vectors: dict[str, ItemVector]
) -> list[ViewFeatureRow]:
    raw_by_stratum: dict[tuple[str, str], dict[str, list[float]]] = {}
    per_view_raw: list[dict[str, float | None]] = []

    for i, view in enumerate(session.views):
        earlier = session.views[:i]
        same_item_earlier = [v for v in earlier if v.item_id == view.item_id]
        item = item_vectors[view.item_id]

        near_substitute_coview_count = None
        if item.near_substitute_set_id is not None:
            window_start = view.start - COMPARISON_WINDOW_MS
            near_substitute_coview_count = sum(
                1
                for v in earlier
                if item_vectors[v.item_id].near_substitute_set_id == item.near_substitute_set_id
                and v.item_id != view.item_id
                and window_start <= v.start <= view.start
            )

        ctx = ItemContext(
            item_id=view.item_id,
            surface="category",
            mode=view.mode,
            pointer_type="mouse",
            category=item.category,
            prior_view_starts_for_item=tuple(v.start for v in same_item_earlier),
            prior_view_categories=tuple(item_vectors[v.item_id].category for v in earlier),
            active_query_token_count=_active_query_token_count(session, view.start),
            near_substitute_coview_count=near_substitute_coview_count,
        )
        window = seal_window_for_view(view.start, view.end, view.item_id, session.commitment_events)

        raw = {name: fn(session.events, window, ctx) for name, fn in ALL_SIGNALS.items()}
        per_view_raw.append(raw)

        stratum = (view.mode, ctx.surface)
        bucket = raw_by_stratum.setdefault(stratum, {name: [] for name in ALL_SIGNALS})
        for name, value in raw.items():
            if value is not None:
                bucket[name].append(value)

    rows: list[ViewFeatureRow] = []
    for view, raw in zip(session.views, per_view_raw):
        stratum = (view.mode, "category")
        population = raw_by_stratum[stratum]
        normalized = {name: z_score(v, population[name]) if v is not None else None for name, v in raw.items()}
        composite_results = compute_composites(normalized)

        other_starts = [v.start for v in session.views if v.item_id == view.item_id and v is not view]
        fast_skip = is_fast_skip(
            view_duration_ms=view.end - view.start,
            item_id=view.item_id,
            view_start=view.start,
            commitment_events=session.commitment_events,
            other_view_starts_for_item=other_starts,
        )

        rows.append(
            ViewFeatureRow(
                session_id=session.session_id,
                archetype_name=session.archetype_name,
                item_id=view.item_id,
                mode=view.mode,
                surface="category",
                utility=view.utility,
                committed=view.committed,
                is_fast_skip=fast_skip,
                composites={f: composite_results[f].value for f in FAMILIES},
                availability={f: composite_results[f].availability for f in FAMILIES},
            )
        )
    return rows
