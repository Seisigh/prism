"""Invented brand identities + text-side brand scrubbing.

BUILD_BRIEF.md §5.3: "The risk lives in text, not in pixels." This module
is the enforcement point for non-negotiable #2 (no real brand names in any
served text). Two independent layers:

1. Served titles/descriptions/specs are *generated* from product_type +
   structured attributes, never copied from ABO's `item_name` or `brand`
   fields, so a real brand string never has a chance to enter served text
   by construction.
2. `strip_known_brand_strings` is defense in depth over free-ish text we do
   derive from source (bullet points, keywords): it removes the item's own
   ABO brand string plus a denylist of common real-world brand/retailer
   tokens, case-insensitively, whole-word.
"""
from __future__ import annotations

import hashlib
import re

# Deterministic procedural brand name generator: two word banks + a
# generator pattern, so names read as plausible without being real.
_PREFIXES = [
    "North", "Kessler", "Varro", "Solace", "Amble", "Fen", "Loft", "Birch",
    "Coastal", "Harlow", "Quiet", "Marrow", "Petal", "Slate", "Gable",
    "Thistle", "Vantage", "Ridgeline", "Clover", "Bramble", "Holt", "Ferro",
    "Linden", "Oakmoor", "Paloma", "Wren", "Copper", "Meridian", "Hearth",
    "Basin", "Cedarwick", "Dunmore", "Elmcourt", "Foundry", "Greylock",
]
_SUFFIXES = [
    "& Vale", "& Pine", "& Co.", "Supply Co.", "Home", "Goods", "Works",
    "Studio", "House", "Collective", "Trading Co.", "& Sons", "Standard",
    "Line", "Labs", "Provisions", "", "", "",
]
_TIER_BY_HASH = ["value", "value", "standard", "standard", "standard", "premium"]

# Common real-world brand / retailer tokens. Defense in depth only — served
# text is generated and never copies source brand strings, so this list
# exists to catch incidental mentions inside bullet-point text we reuse.
_DENYLIST = {
    "amazon", "amazonbasics", "nike", "adidas", "ikea", "target", "walmart",
    "apple", "samsung", "sony", "lg", "dell", "hp", "hewlett", "packard",
    "logitech", "bose", "jbl", "beats", "levis", "levi's", "gap", "hanes",
    "fossil", "casio", "seiko", "gucci", "prada", "coach", "kate spade",
    "michael kors", "ralph lauren", "tommy hilfiger", "calvin klein",
    "under armour", "puma", "reebok", "new balance", "vans", "converse",
    "crocs", "skechers", "columbia", "north face", "patagonia", "carhartt",
    "dewalt", "makita", "bosch", "black+decker", "black & decker", "3m",
    "kohler", "moen", "delta faucet", "whirlpool", "ge", "general electric",
    "kitchenaid", "cuisinart", "ninja", "instant pot", "keurig", "nespresso",
    "yeti", "rtic", "tupperware", "rubbermaid", "pyrex", "corelle",
    "hallmark", "disney", "marvel", "lego", "hasbro", "mattel", "nerf",
    "fisher-price", "graco", "chicco", "britax", "pampers", "huggies",
    "johnson & johnson", "neutrogena", "olay", "dove", "nivea", "loreal",
    "l'oreal", "maybelline", "revlon", "clinique", "estee lauder", "mac",
    "sephora", "ulta", "wayfair", "overstock", "pottery barn", "west elm",
    "crate & barrel", "ashley furniture", "serta", "sealy", "tempurpedic",
    "tempur-pedic", "casper",
}


def brand_name_pool(size: int = 150) -> list[dict]:
    """Deterministic invented brand list: {name, tier}."""
    pool: dict[str, str] = {}
    i = 0
    while len(pool) < size:
        prefix = _PREFIXES[i % len(_PREFIXES)]
        suffix = _SUFFIXES[(i // len(_PREFIXES)) % len(_SUFFIXES)]
        name = f"{prefix} {suffix}".strip()
        if name not in pool:
            digest = hashlib.sha1(name.encode()).hexdigest()
            tier = _TIER_BY_HASH[int(digest[:2], 16) % len(_TIER_BY_HASH)]
            pool[name] = tier
        i += 1
    return [{"name": n, "tier": t} for n, t in pool.items()]


_POOL = brand_name_pool()


def assign_brand(item_id: str) -> dict:
    """Deterministic invented brand for an item, stable across rebuilds."""
    digest = hashlib.sha1(item_id.encode()).hexdigest()
    idx = int(digest[:8], 16) % len(_POOL)
    return _POOL[idx]


def _source_brand_variants(raw_brand_values: list[str]) -> set[str]:
    variants: set[str] = set()
    for v in raw_brand_values:
        v = v.strip()
        if not v:
            continue
        variants.add(v.lower())
        # "Amazon Brand - find." style prefixes: also ban the trailing token
        tail = v.split("-")[-1].strip().strip(".").lower()
        if tail:
            variants.add(tail)
    return variants


def strip_known_brand_strings(text: str, raw_brand_values: list[str]) -> str:
    """Remove the item's own source brand string plus the denylist,
    whole-word, case-insensitive. Collapses resulting whitespace."""
    if not text:
        return text
    variants = _source_brand_variants(raw_brand_values) | _DENYLIST
    out = text
    for variant in sorted(variants, key=len, reverse=True):
        if not variant:
            continue
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(variant) + r"(?![a-z0-9])", re.IGNORECASE)
        out = pattern.sub("", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return out.strip(" -,")


def contains_known_brand_string(text: str, raw_brand_values: list[str]) -> bool:
    if not text:
        return False
    variants = _source_brand_variants(raw_brand_values) | _DENYLIST
    lowered = text.lower()
    return any(
        re.search(r"(?<![a-z0-9])" + re.escape(v) + r"(?![a-z0-9])", lowered)
        for v in variants
        if v
    )
