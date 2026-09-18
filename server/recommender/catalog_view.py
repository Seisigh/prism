"""The recommender's view of the catalog: item embeddings (sim/embedding.py's
7-dim taste-vector space, so cosine similarity against a session's taste
vector is meaningful) joined with the raw price_cents/category fields the
catalog build produces. sim/embedding.py's own vector already carries a
per-*category* z-scored price dimension (`price_z`), which is the wrong
thing for "price-band filters" (BUILD_BRIEF.md §12) -- that needs real,
comparable price buckets across the whole catalog, not a per-category
relative position, so this module reads price_cents from data/catalog.json
directly rather than trying to recover it from the embedding.

Context-catalog items only by default: §5.1 makes the context catalog
(not the 60-item instrumented core) "the recommender's candidate pool."
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sim.embedding import build_item_vectors

CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "catalog.json"

# Coarse, fixed price bands in cents -- a declared bucketing, not fit to
# the catalog's own price distribution, so it doesn't shift if the
# catalog is rebuilt with different items.
PRICE_BANDS: list[tuple[float, float]] = [
    (0, 2500), (2500, 5000), (5000, 10000), (10000, 25000), (25000, float("inf")),
]


@dataclass(frozen=True)
class CatalogItem:
    item_id: str
    category: str
    price_cents: int
    price_band: int
    vector: tuple[float, ...]


def price_band_index(price_cents: int) -> int:
    for i, (lo, hi) in enumerate(PRICE_BANDS):
        if lo <= price_cents < hi:
            return i
    return len(PRICE_BANDS) - 1


def load_catalog_items(context_only: bool = True) -> dict[str, CatalogItem]:
    item_vectors = build_item_vectors()
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = raw["context_items"] if context_only else raw["context_items"] + raw["core_items"]

    out: dict[str, CatalogItem] = {}
    for item in items:
        vec = item_vectors.get(item["item_id"])
        if vec is None:
            continue
        out[item["item_id"]] = CatalogItem(
            item_id=item["item_id"],
            category=item["category"],
            price_cents=item["price_cents"],
            price_band=price_band_index(item["price_cents"]),
            vector=vec.vector,
        )
    return out


def filter_candidates(
    items: dict[str, CatalogItem],
    category: str | None = None,
    price_band: int | None = None,
    exclude_item_ids: frozenset[str] = frozenset(),
) -> dict[str, CatalogItem]:
    return {
        item_id: item
        for item_id, item in items.items()
        if item_id not in exclude_item_ids
        and (category is None or item.category == category)
        and (price_band is None or item.price_band == price_band)
    }
