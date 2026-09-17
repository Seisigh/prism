"""Item embeddings the simulator's agents reason about — built from the
*real* catalog (data/catalog.json), not synthetic placeholder vectors.
Every dimension here is a real, observable catalog attribute; an agent's
taste vector is a set of weights over these same dimensions, so "utility"
is a legible dot product an ablation can later attribute, not a black box.

Deliberately low-dimensional and interpretable — this is Gate 1's
grounding layer, not a learned embedding model. That's a feature: the
whole point of the simulator is a *declared* generative process (§11),
and a declared process needs declared, inspectable inputs.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

DIMENSIONS = [
    "price_z",  # standardized log-price within category
    "rating",  # 1..5
    "review_count_log",  # log1p(review_count)
    "on_sale",  # 1.0 if anchor_price_cents is set, else 0.0
    "description_length",  # short=0, medium=0.5, long=1.0
    "gallery_size",  # 1..6, min-max scaled to 0..1
    "brand_tier",  # value=0, standard=0.5, premium=1.0
]

_BAND_SCORE = {"short": 0.0, "medium": 0.5, "long": 1.0}
_TIER_SCORE = {"value": 0.0, "standard": 0.5, "premium": 1.0}


@dataclass(frozen=True)
class ItemVector:
    item_id: str
    category: str
    vector: tuple[float, ...]  # aligned with DIMENSIONS


def _load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"{CATALOG_PATH} not found — run `python -m catalog.build` first. "
            "The simulator embeds the real catalog, not a synthetic stand-in."
        )
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def build_item_vectors() -> dict[str, ItemVector]:
    data = _load_catalog()
    items = data["context_items"] + data["core_items"]

    by_category_prices: dict[str, list[float]] = {}
    for item in items:
        by_category_prices.setdefault(item["category"], []).append(math.log1p(item["price_cents"] / 100))

    category_stats = {}
    for cat, prices in by_category_prices.items():
        mean = sum(prices) / len(prices)
        var = sum((p - mean) ** 2 for p in prices) / max(1, len(prices) - 1)
        category_stats[cat] = (mean, math.sqrt(var) or 1.0)

    gallery_sizes = [1 + len(i["images"]["detail_gallery"]) for i in items if i.get("images")]
    max_gallery = max(gallery_sizes) if gallery_sizes else 1

    vectors: dict[str, ItemVector] = {}
    for item in items:
        if not item.get("images"):
            continue
        mean, std = category_stats[item["category"]]
        price_z = (math.log1p(item["price_cents"] / 100) - mean) / std
        gallery_n = 1 + len(item["images"]["detail_gallery"])
        vec = (
            price_z,
            item["rating"],
            math.log1p(item["review_count"]),
            1.0 if item["anchor_price_cents"] else 0.0,
            _BAND_SCORE[item["description_band"]],
            gallery_n / max_gallery,
            _TIER_SCORE[item["brand_tier"]],
        )
        vectors[item["item_id"]] = ItemVector(item_id=item["item_id"], category=item["category"], vector=vec)
    return vectors
