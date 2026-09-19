"""Synthetic commerce attributes generated from realistic distributions.

Per §5.6: a store where everything costs $24.99 and has 4.5 stars reads as
fake within three seconds. Every distribution here is deliberately
non-uniform and category-aware.
"""
from __future__ import annotations

import math
import random

# (median price in dollars, log-normal sigma) per category. Medians are
# rough real-world anchors for each category's typical item; sigma widens
# categories that genuinely span cheap-to-premium (furniture, jewelry).
CATEGORY_PRICE_PARAMS: dict[str, tuple[float, float]] = {
    "Home & Furniture": (140.0, 0.75),
    "Kitchen & Dining": (28.0, 0.65),
    "Bed & Bath": (45.0, 0.6),
    "Rugs & Decor": (60.0, 0.7),
    "Lighting": (55.0, 0.65),
    "Shoes & Footwear": (58.0, 0.5),
    "Jewelry & Accessories": (42.0, 0.9),
    "Beauty & Personal Care": (18.0, 0.55),
    "Health & Wellness": (22.0, 0.5),
    "Pet Supplies": (20.0, 0.6),
    "Outdoor & Garden": (48.0, 0.7),
    "Office & Stationery": (14.0, 0.55),
    "Grocery & Gourmet": (9.0, 0.45),
    "Sports & Fitness": (30.0, 0.6),
    "Electronics Accessories": (19.0, 0.65),
    "Toys & Games": (17.0, 0.55),
    "Travel & Luggage": (65.0, 0.6),
    "Arts & Crafts": (16.0, 0.55),
    "Music": (35.0, 0.6),
}
_DEFAULT_PRICE_PARAMS = (30.0, 0.6)


def generate_price_cents(category: str, rng: random.Random) -> int:
    median, sigma = CATEGORY_PRICE_PARAMS.get(category, _DEFAULT_PRICE_PARAMS)
    mu = math.log(median)
    raw = rng.lognormvariate(mu, sigma)
    raw = max(2.5, min(raw, median * 12))  # clip extreme tail so nothing absurd renders
    roll = rng.random()
    if roll < 0.70:
        cents = int(raw) * 100 + 99
    elif roll < 0.85:
        cents = int(raw) * 100 + 95
    else:
        cents = int(round(raw * 100))
    return max(199, cents)


def maybe_anchor_price_cents(price_cents: int, rng: random.Random) -> int | None:
    if rng.random() >= 0.35:
        return None
    discount = rng.uniform(0.10, 0.40)
    anchor = int(round(price_cents / (1 - discount)))
    # keep the .99/.95 snap on the anchor too, it reads more real
    if rng.random() < 0.7:
        anchor = (anchor // 100) * 100 + 99
    return anchor


def generate_rating(rng: random.Random) -> float:
    # Left-skewed around ~4.3: draw from a skewed beta and remap to [1, 5].
    x = rng.betavariate(6.0, 2.2)  # skews high, occasional low draws
    rating = 1.0 + x * 4.0
    return round(min(5.0, max(1.0, rating)), 1)


def generate_review_count(rng: random.Random) -> int:
    # Heavy Pareto tail: most items 20-400, some near-zero, rare 20k+.
    roll = rng.random()
    if roll < 0.08:
        return rng.randint(0, 19)
    if roll < 0.93:
        return rng.randint(20, 400)
    if roll < 0.99:
        return rng.randint(401, 3000)
    return rng.randint(20000, 60000)


# Season is a merchandising attribute only (close-out item 4): which
# rail an item surfaces on and whether it gets a seasonal badge. It must
# never reach the feature pipeline, ItemContext, or the ranker — see
# server/features/ (no import of this module or catalog/ anywhere there,
# enforced by the same import-linter contract that already keeps
# `ingest`/`models`/`recommender` out). Most items aren't seasonal at
# all; a handful of categories get a modest bias toward the season their
# real-world equivalent actually skews toward, everything else is
# uniform across the five real seasons.
_SEASON_BIAS: dict[str, dict[str, float]] = {
    "Outdoor & Garden": {"spring": 0.30, "summer": 0.35, "fall": 0.10, "winter": 0.05, "holiday": 0.05},
    "Sports & Fitness": {"spring": 0.20, "summer": 0.30, "fall": 0.15, "winter": 0.10, "holiday": 0.05},
    "Travel & Luggage": {"spring": 0.15, "summer": 0.35, "fall": 0.10, "winter": 0.10, "holiday": 0.10},
    "Lighting": {"spring": 0.05, "summer": 0.05, "fall": 0.10, "winter": 0.15, "holiday": 0.35},
    "Toys & Games": {"spring": 0.05, "summer": 0.10, "fall": 0.05, "winter": 0.10, "holiday": 0.45},
    "Jewelry & Accessories": {"spring": 0.05, "summer": 0.05, "fall": 0.05, "winter": 0.10, "holiday": 0.35},
    "Bed & Bath": {"spring": 0.10, "summer": 0.10, "fall": 0.15, "winter": 0.30, "holiday": 0.05},
}
_SEASON_NONE_RATE = 0.55  # most items are not seasonal at all
_SEASONS = ("spring", "summer", "fall", "winter", "holiday")
_DEFAULT_SEASON_WEIGHTS = {s: 1.0 / len(_SEASONS) for s in _SEASONS}


def generate_season(category: str, rng: random.Random) -> str:
    if rng.random() < _SEASON_NONE_RATE:
        return "none"
    weights = _SEASON_BIAS.get(category, _DEFAULT_SEASON_WEIGHTS)
    seasons = list(weights.keys())
    return rng.choices(seasons, weights=list(weights.values()), k=1)[0]


def generate_stock(rng: random.Random) -> tuple[str, str | None]:
    roll = rng.random()
    if roll < 0.03:
        return "out_of_stock", "Currently out of stock"
    if roll < 0.12:
        return "low_stock", f"Only {rng.randint(2, 5)} left"
    return "in_stock", None


def generate_shipping_line(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.55:
        days = rng.choice([2, 3])
        return f"Arrives in {days} days"
    if roll < 0.85:
        days = rng.choice([4, 5, 6])
        return f"Arrives in {days} days"
    return "Free shipping on this item"


def generate_review_texts(rating: float, n: int, rng: random.Random) -> list[dict]:
    """Small set of synthetic review snippets. Every one is visibly marked
    synthetic by the caller (see COPY.md §3) — never omit the marker.

    Samples each star bucket's pool without replacement (falling back to
    replacement only once a pool is exhausted) so a short review list
    never repeats the identical sentence back to back.
    """
    positive = [
        "Held up well after the first few weeks of regular use.",
        "Exactly the size I expected from the listing photos.",
        "Good value for the price point.",
        "Arrived well packaged and set up quickly.",
        "Color in person matches the photos closely.",
    ]
    mixed = [
        "Does the job, though the finish shows wear faster than I'd like.",
        "A bit smaller than I pictured, but still usable.",
        "Fine overall; instructions could be clearer.",
    ]
    negative = [
        "Stopped working the way I expected after a short time.",
        "Not quite what the listing implied.",
    ]
    out = []
    remaining: dict[int, list[str]] = {}
    for i in range(n):
        if rating >= 4.2:
            pool, stars = positive, rng.choice([4, 5, 5])
        elif rating >= 3.3:
            pool, stars = mixed, rng.choice([3, 4])
        else:
            pool, stars = negative, rng.choice([1, 2, 3])
        bucket_key = id(pool)
        if bucket_key not in remaining or not remaining[bucket_key]:
            remaining[bucket_key] = pool[:]
            rng.shuffle(remaining[bucket_key])
        body = remaining[bucket_key].pop()
        out.append({"stars": stars, "body": body, "synthetic": True})
    return out
