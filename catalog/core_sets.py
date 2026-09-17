"""Builds the ~60-item instrumented core: near-substitute sets of same-
product-type items that vary exactly one attribute at a time (§5.4).

Core items are a *disjoint* pool from the 750-item context catalog (see
STATE.md for why: §12 scopes the recommender's candidate generation to
"the context catalog", which only makes sense if core is a separate set,
not a labeled subset of the same 750). Both pools are logged identically;
only the core is used for controlled measurement, and only core items get
the §5.7 placement boost.
"""
from __future__ import annotations

import random

from catalog.candidates import Candidate

# product_type -> how many items to draw into one near-substitute set.
# Chosen for real availability (see STATE.md coverage audit) and for
# forming a plausible "same near-substitute set" grouping a comparison-
# mode shopper would actually treat as substitutes.
CORE_SET_SPECS = [
    ("CHAIR", 5),
    ("SOFA", 5),
    ("TABLE", 5),
    ("LAMP", 5),
    ("RUG", 5),
    ("SHOES", 5),
    ("BOOT", 5),
    ("PILLOW", 5),
    ("EARRING", 5),
    ("PLANTER", 5),
    ("BACKPACK", 5),
    ("COFFEE", 5),
]

VARIED_ATTRIBUTES = [
    "price",
    "rating_count",
    "description_length",
    "gallery_size",
    "copy_framing",
]


def build_core_sets(
    candidates: list[Candidate], rng: random.Random
) -> tuple[list[tuple[str, str, list[Candidate]]], set[str]]:
    """Returns (sets, used_source_ids). Each set is
    (set_id, varied_attribute, [5 candidates])."""
    by_type: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_type.setdefault(c.product_type, []).append(c)
    for lst in by_type.values():
        rng.shuffle(lst)

    sets: list[tuple[str, str, list[Candidate]]] = []
    used: set[str] = set()
    for i, (product_type, n) in enumerate(CORE_SET_SPECS):
        pool = [c for c in by_type.get(product_type, []) if c.source_item_id not in used]
        if len(pool) < n:
            raise ValueError(
                f"core set {product_type} needs {n} candidates, only {len(pool)} available"
            )
        chosen = pool[:n]
        for c in chosen:
            used.add(c.source_item_id)
        varied = VARIED_ATTRIBUTES[i % len(VARIED_ATTRIBUTES)]
        set_id = f"core-{product_type.lower()}-{i:02d}"
        sets.append((set_id, varied, chosen))
    return sets, used
