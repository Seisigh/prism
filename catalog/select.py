"""Orchestrates candidate selection -> generated CatalogItem assembly for
both the context catalog (~750) and the instrumented core (~60).

Images are NOT attached here; images.py fills `ImageSet` after this module
produces items, keyed by item_id, so this module can run and be inspected
(coverage reports, spot-check sampling) without touching the network for
every image.
"""
from __future__ import annotations

import random

from catalog.brands import assign_brand
from catalog.candidates import Candidate, iter_candidates
from catalog.core_sets import build_core_sets
from catalog.descriptions import generate_description
from catalog.schema import CatalogItem, ReviewSnippet
from catalog.synth_attributes import (
    generate_price_cents,
    generate_rating,
    generate_review_count,
    generate_review_texts,
    generate_shipping_line,
    generate_stock,
    maybe_anchor_price_cents,
)
from catalog.titles import generate_title

CONTEXT_TARGET = 750
DESCRIPTION_BAND_WEIGHTS = [("short", 0.25), ("medium", 0.5), ("long", 0.25)]
_GALLERY_RAMP = [1, 2, 3, 4, 6]
_REVIEW_COUNT_RAMP = [3, 40, 220, 1200, 22000]
_DESC_BAND_RAMP = ["short", "short", "medium", "long", "long"]


def _weighted_choice(weights: list[tuple[str, float]], rng: random.Random) -> str:
    total = sum(w for _, w in weights)
    r = rng.uniform(0, total)
    upto = 0.0
    for label, w in weights:
        upto += w
        if r <= upto:
            return label
    return weights[-1][0]


_UNIT_ABBREV = {
    "inches": "in",
    "inch": "in",
    "feet": "ft",
    "foot": "ft",
    "pounds": "lb",
    "pound": "lb",
    "ounces": "oz",
    "ounce": "oz",
    "centimeters": "cm",
    "millimeters": "mm",
    "kilograms": "kg",
    "grams": "g",
}


def _fmt_measurement(value: float, unit: str) -> str:
    abbrev = _UNIT_ABBREV.get(unit.lower(), unit)
    return f"{value:g} {abbrev}"


def _spec_table(candidate: Candidate, brand: str) -> dict[str, str]:
    from catalog.brands import strip_known_brand_strings

    listing = candidate.listing
    spec: dict[str, str] = {"Brand": brand}

    def first_en(field_name: str) -> str | None:
        for e in listing.get(field_name, []) or []:
            if e.get("language_tag", "").startswith("en") and e.get("value"):
                return strip_known_brand_strings(str(e["value"]), candidate.raw_brand_values)
        return None

    for field_name, label in (
        ("color", "Color"),
        ("material", "Material"),
        ("pattern", "Pattern"),
        ("style", "Style"),
        ("finish_type", "Finish"),
        ("fabric_type", "Fabric"),
        ("item_shape", "Shape"),
    ):
        v = first_en(field_name)
        if v:
            # Some raw ABO attribute values are snake_case tokens
            # ("spun_polyester", "wood_grain") rather than prose — an
            # underscore is never meaningful punctuation in served text.
            spec[label] = v.replace("_", " ").strip(" -,")[:60]

    dims = listing.get("item_dimensions")
    if isinstance(dims, dict):
        parts = []
        for axis in ("length", "width", "height"):
            nv = dims.get(axis, {}).get("normalized_value", {})
            if nv.get("value") and nv.get("unit"):
                parts.append(_fmt_measurement(nv["value"], nv["unit"]))
        if parts:
            spec["Dimensions"] = " x ".join(parts)

    weight = listing.get("item_weight")
    if isinstance(weight, list) and weight:
        w = weight[0]
        if w.get("normalized_value"):
            nv = w["normalized_value"]
            if nv.get("value") is not None:
                spec["Weight"] = _fmt_measurement(nv["value"], nv.get("unit", ""))

    return spec


def _assemble_item(
    candidate: Candidate,
    rng: random.Random,
    is_core: bool,
    set_id: str | None,
    varied_attribute: str | None,
    set_anchor: dict | None,
) -> CatalogItem:
    brand_info = assign_brand(candidate.source_item_id)
    brand = brand_info["name"]
    title = generate_title(candidate.listing, candidate.product_type, rng)

    framing = set_anchor["copy_framing"] if set_anchor else rng.choice(["feature_led", "benefit_led"])
    band = set_anchor["description_band"] if set_anchor else _weighted_choice(DESCRIPTION_BAND_WEIGHTS, rng)

    description, bullets = generate_description(
        candidate.listing, candidate.raw_brand_values, candidate.type_info.category, band, framing, rng
    )

    price_cents = set_anchor["price_cents"] if set_anchor else generate_price_cents(
        candidate.type_info.category, rng
    )
    anchor_price_cents = maybe_anchor_price_cents(price_cents, rng)
    rating = generate_rating(rng)
    review_count = set_anchor["review_count"] if set_anchor else generate_review_count(rng)
    stock_status, stock_label = generate_stock(rng)
    shipping_line = generate_shipping_line(rng)

    badges: list[str] = []
    if rating >= 4.4 and rng.random() < 0.08:
        badges.append("Best Seller")
    elif rng.random() < 0.03:
        badges.append("Overall Pick")

    n_reviews_to_show = rng.randint(3, 6)
    reviews = [
        ReviewSnippet(stars=r["stars"], body=r["body"], synthetic=r["synthetic"])
        for r in generate_review_texts(rating, n_reviews_to_show, rng)
    ]

    return CatalogItem(
        item_id=candidate.item_id,
        title=title,
        category=candidate.type_info.category,
        verticals=list(candidate.type_info.verticals),
        gender=candidate.gender,
        age_band=candidate.age_band,
        brand=brand,
        brand_tier=brand_info["tier"],
        description=description,
        description_band=band,
        copy_framing=framing,
        bullets=bullets,
        spec=_spec_table(candidate, brand),
        price_cents=price_cents,
        anchor_price_cents=anchor_price_cents,
        rating=rating,
        review_count=review_count,
        stock_status=stock_status,
        stock_label=stock_label,
        shipping_line=shipping_line,
        images=None,
        is_core=is_core,
        near_substitute_set_id=set_id,
        varied_attribute=varied_attribute,
        badges=badges,
        alt_text=f"{title} product photo",
        reviews=reviews,
        _source_item_id=candidate.source_item_id,
        _product_type=candidate.product_type,
    )


def _water_fill_context_quota(
    by_category: dict[str, list[Candidate]], target: int
) -> dict[str, int]:
    categories = list(by_category.keys())
    quotas = {c: 0 for c in categories}
    remaining_target = target
    active = {c for c in categories if by_category[c]}
    while remaining_target > 0 and active:
        share = max(1, remaining_target // len(active))
        progressed = False
        for c in list(active):
            available = len(by_category[c]) - quotas[c]
            if available <= 0:
                active.discard(c)
                continue
            take = min(share, available, remaining_target)
            if take <= 0:
                continue
            quotas[c] += take
            remaining_target -= take
            progressed = True
            if quotas[c] >= len(by_category[c]):
                active.discard(c)
            if remaining_target <= 0:
                break
        if not progressed:
            break
    return quotas


def build_catalog(seed: int = 20260917) -> dict:
    rng = random.Random(seed)
    all_candidates = iter_candidates()

    core_sets, core_used_ids = build_core_sets(all_candidates, random.Random(seed + 1))
    remaining = [c for c in all_candidates if c.source_item_id not in core_used_ids]

    by_category: dict[str, list[Candidate]] = {}
    for c in remaining:
        by_category.setdefault(c.type_info.category, []).append(c)
    for lst in by_category.values():
        rng.shuffle(lst)

    quotas = _water_fill_context_quota(by_category, CONTEXT_TARGET)

    context_items: list[CatalogItem] = []
    for category, quota in quotas.items():
        for c in by_category[category][:quota]:
            context_items.append(_assemble_item(c, rng, is_core=False, set_id=None, varied_attribute=None, set_anchor=None))

    core_items: list[CatalogItem] = []
    for set_id, varied_attribute, members in core_sets:
        category = members[0].type_info.category
        anchor_price = generate_price_cents(category, rng)
        anchor_band = _weighted_choice(DESCRIPTION_BAND_WEIGHTS, rng)
        anchor_framing = rng.choice(["feature_led", "benefit_led"])
        anchor_review_count = generate_review_count(rng)

        for i, member in enumerate(members):
            set_anchor = {
                "price_cents": anchor_price,
                "description_band": anchor_band,
                "copy_framing": anchor_framing,
                "review_count": anchor_review_count,
            }
            if varied_attribute == "price":
                base = anchor_price
                ramp = [0.65, 0.85, 1.0, 1.25, 1.6]
                set_anchor["price_cents"] = max(199, int(base * ramp[i]))
            elif varied_attribute == "rating_count":
                set_anchor["review_count"] = _REVIEW_COUNT_RAMP[i]
            elif varied_attribute == "description_length":
                set_anchor["description_band"] = _DESC_BAND_RAMP[i]
            elif varied_attribute == "copy_framing":
                set_anchor["copy_framing"] = "feature_led" if i < 3 else "benefit_led"
            # gallery_size is applied later in images.py, once we know how
            # many source images actually exist per item; recorded here so
            # images.py can look it up.
            item = _assemble_item(
                member, rng, is_core=True, set_id=set_id, varied_attribute=varied_attribute, set_anchor=set_anchor
            )
            core_items.append(item)

    return {
        "context_items": context_items,
        "core_items": core_items,
        "quotas": quotas,
        "gallery_ramp": _GALLERY_RAMP,
        "core_sets": [(sid, va, [m.item_id for m in members]) for sid, va, members in core_sets],
    }
