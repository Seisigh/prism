"""Builds served description text and "about this item" bullets from
source bullet points, brand-scrubbed, normalized into fixed length bands.

§5.4 calls for an LLM normalization pass. No LLM API key is configured in
this build environment, so this is a deterministic rule-based normalizer
instead: bullets are cleaned, deduped, and assembled into template
sentences, then padded or trimmed to hit the target character band. This
keeps description length a genuinely controlled variable (the point of the
requirement) without a network dependency on a model provider. Logged as
a substitution in STATE.md — swapping in a real LLM call later is a
drop-in replacement for `_assemble` since the band contract doesn't change.
"""
from __future__ import annotations

import random

from catalog.brands import strip_known_brand_strings

BAND_RANGES = {
    "short": (80, 150),
    "medium": (180, 290),
    "long": (320, 480),
}

_FEATURE_TEMPLATES = [
    "Made with {bullet_lower}.",
    "Features {bullet_lower}.",
    "Constructed with {bullet_lower}.",
    "Finished with {bullet_lower}.",
]
_BENEFIT_TEMPLATES = [
    "Built to make everyday use easier, with {bullet_lower}.",
    "Designed so {bullet_lower} fits naturally into daily use.",
    "Keeps things simple: {bullet_lower}.",
]

_GENERIC_FILLER = [
    "Fits easily into most everyday routines.",
    "A practical pick for the {category_lower} category.",
    "Designed to hold up to regular use.",
    "Straightforward to use out of the box.",
]


def _clean_bullets(raw_bullets: list[dict], raw_brand_values: list[str]) -> list[str]:
    seen = set()
    cleaned = []
    for b in raw_bullets or []:
        tag = b.get("language_tag", "")
        if not tag.startswith("en"):
            continue
        text = strip_known_brand_strings(b.get("value", ""), raw_brand_values).strip(" -,.")
        if not text or len(text) < 3:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def _assemble(bullets: list[str], band: str, framing: str, category: str, rng: random.Random) -> str:
    lo, hi = BAND_RANGES[band]
    templates = _FEATURE_TEMPLATES if framing == "feature_led" else _BENEFIT_TEMPLATES
    sentences: list[str] = []
    pool = bullets[:] if bullets else ["a durable everyday design"]
    idx = 0
    while sum(len(s) + 1 for s in sentences) < lo and idx < 12:
        bullet = pool[idx % len(pool)]
        template = templates[idx % len(templates)]
        sentences.append(template.format(bullet_lower=_lower_first(bullet)))
        idx += 1
    filler_idx = 0
    while sum(len(s) + 1 for s in sentences) < lo and filler_idx < len(_GENERIC_FILLER):
        sentences.append(_GENERIC_FILLER[filler_idx].format(category_lower=category.lower()))
        filler_idx += 1
    text = " ".join(sentences)
    if len(text) > hi:
        text = text[: hi - 1].rsplit(" ", 1)[0] + "."
    return text


def generate_description(
    listing: dict,
    raw_brand_values: list[str],
    category: str,
    band: str,
    framing: str,
    rng: random.Random,
) -> tuple[str, list[str]]:
    """Returns (flowing description, about-this-item bullets)."""
    bullets = _clean_bullets(listing.get("bullet_point", []), raw_brand_values)
    description = _assemble(bullets, band, framing, category, rng)
    about_bullets = [b[:1].upper() + b[1:] for b in bullets[:6]]
    if not about_bullets:
        about_bullets = ["Everyday design intended for regular use."]
    return description, about_bullets
