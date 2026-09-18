"""Backs the admin console's session-detail signal table (§6.7 item 2)
and signal-distributions view (§6.7 item 5) -- both read real stored
event logs through the exact same `server/features/live.py` pipeline the
live scoring path uses, so what the admin sees is never a separate,
possibly-diverging code path from what actually scored the session.
"""
from __future__ import annotations

from collections import defaultdict
from uuid import UUID

import asyncpg

from server.catalog_store import get_store
from server.features.labels import tier1_label
from server.features.live import LiveView, extract_session_features_with_raw, view_is_fast_skip
from server.features.replay import recompute_session
from server.ingest.live_scoring import _commitment_events_from_rows, _item_vectors
from server.ingest.store import get_session_events
from server.models import ranker_store


def _brand_tokens(store) -> set[str]:
    tokens: set[str] = set()
    for item in store.all_items:
        tokens.update(item["brand"].lower().replace("&", " ").split())
    return tokens


async def get_session_signal_table(pool: asyncpg.Pool, session_id: UUID) -> list[dict]:
    """One row per item view: item, surface, mode, every signal's raw
    value + normalized value + availability, the ranker's predicted
    interest (raw + calibrated), and the label that actually
    materialized (committed / fast_skip / ambiguous)."""
    event_rows = await get_session_events(pool, session_id)
    if not event_rows:
        return []

    store = get_store()
    near_substitute_set_by_item = {i["item_id"]: i["near_substitute_set_id"] for i in store.core_items if i["near_substitute_set_id"]}
    item_views = recompute_session(event_rows, near_substitute_set_by_item, _brand_tokens(store))
    if not item_views:
        return []

    live_views = [
        LiveView(
            item_id=v.item_id,
            surface=v.surface,
            mode=v.mode,
            start=v.start,
            end=v.end,
            category=store.by_id.get(v.item_id, {}).get("category"),
            near_substitute_set_id=near_substitute_set_by_item.get(v.item_id),
        )
        for v in item_views
    ]
    pairs = extract_session_features_with_raw(event_rows, live_views)
    commitment_events = _commitment_events_from_rows(event_rows)
    item_vectors = _item_vectors()

    rows = []
    for view, live_view, (raw, normalized) in zip(item_views, live_views, pairs):
        _raw_score, p_i = ranker_store.score(view.mode, normalized)
        fast_skip = view_is_fast_skip(live_view, live_views, commitment_events)
        committed = tier1_label(view.item_id, view.start, commitment_events)
        label = "committed" if committed else ("fast_skip" if fast_skip else "ambiguous")

        signals = {}
        for name in raw:
            signals[name] = {
                "raw": raw[name],
                "normalized": normalized[name],
                "available": raw[name] is not None,
            }

        rows.append(
            {
                "item_id": view.item_id,
                "item_known": view.item_id in item_vectors,
                "surface": view.surface,
                "mode": view.mode,
                "start": view.start,
                "end": view.end,
                "duration_ms": view.duration_ms,
                "predicted_p_i": p_i,
                "label": label,
                "signals": signals,
            }
        )
    return rows


async def get_signal_distributions(pool: asyncpg.Pool, session_ids: list[UUID]) -> dict:
    """Per (signal, mode, surface): a coarse histogram of raw values plus
    the availability rate -- across every session given, not just one.
    §6.7 item 5: "This is how you notice that hover is null on every
    detail page, or that a normalizer is producing a degenerate
    distribution, before either one silently corrupts a model." Real
    data only, no synthetic filler -- a stratum with no observations yet
    is reported as such (n=0), never invented.
    """
    store = get_store()
    near_substitute_set_by_item = {i["item_id"]: i["near_substitute_set_id"] for i in store.core_items if i["near_substitute_set_id"]}
    brand_tokens = _brand_tokens(store)

    # signal_name -> (mode, surface) -> list[float | None]
    buckets: dict[str, dict[tuple[str, str], list[float | None]]] = defaultdict(lambda: defaultdict(list))

    for session_id in session_ids:
        event_rows = await get_session_events(pool, session_id)
        if not event_rows:
            continue
        item_views = recompute_session(event_rows, near_substitute_set_by_item, brand_tokens)
        if not item_views:
            continue
        live_views = [
            LiveView(
                item_id=v.item_id,
                surface=v.surface,
                mode=v.mode,
                start=v.start,
                end=v.end,
                category=store.by_id.get(v.item_id, {}).get("category"),
                near_substitute_set_id=near_substitute_set_by_item.get(v.item_id),
            )
            for v in item_views
        ]
        pairs = extract_session_features_with_raw(event_rows, live_views)
        for view, (raw, _normalized) in zip(item_views, pairs):
            for name, value in raw.items():
                buckets[name][(view.mode, view.surface)].append(value)

    out = {}
    for name, by_stratum in buckets.items():
        strata = {}
        for (mode, surface), values in by_stratum.items():
            available = [v for v in values if v is not None]
            strata[f"{mode}|{surface}"] = {
                "mode": mode,
                "surface": surface,
                "n": len(values),
                "n_available": len(available),
                "availability_rate": (len(available) / len(values)) if values else 0.0,
                "histogram": _histogram(available),
            }
        out[name] = strata
    return out


def _histogram(values: list[float], n_bins: int = 10) -> dict:
    if not values:
        return {"bin_edges": [], "counts": []}
    lo, hi = min(values), max(values)
    if lo == hi:
        return {"bin_edges": [lo, hi], "counts": [len(values)]}
    width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for v in values:
        idx = min(n_bins - 1, int((v - lo) / width))
        counts[idx] += 1
    edges = [lo + i * width for i in range(n_bins + 1)]
    return {"bin_edges": edges, "counts": counts}
