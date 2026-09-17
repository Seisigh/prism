"""Filters raw ABO listings down to usable candidates and normalizes the
fields the rest of the pipeline needs, before any generation happens."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from catalog.download import iter_all_raw_listings
from catalog.taxonomy import PRODUCT_TYPE_MAP, TypeInfo, infer_age_band, infer_gender

# Product-is-its-branding risk: team/franchise jerseys, licensed-logo
# merchandise. Keyword screen ahead of the manual §5.3 spot-check, not a
# replacement for it — see catalog/spotcheck.py.
_BRANDING_RISK_KEYWORDS = re.compile(
    r"\b(jersey|licensed|logo mug|monogram|fan gear|team colors|collegiate|"
    r"varsity|championship ring|trophy)\b",
    re.IGNORECASE,
)


@dataclass
class Candidate:
    item_id: str  # our own id, stable hash of the source id
    source_item_id: str
    product_type: str
    type_info: TypeInfo
    age_band: str
    gender: str
    raw_brand_values: list[str]
    listing: dict
    main_image_id: str
    other_image_ids: list[str]
    text_blob: str  # for keyword screens (title/keywords/bullets, lowercased)


def _first_en_values(field_values: list[dict]) -> list[str]:
    return [
        e.get("value", "")
        for e in (field_values or [])
        if e.get("language_tag", "").startswith("en") and e.get("value")
    ]


def _make_item_id(source_item_id: str) -> str:
    return "p-" + hashlib.sha1(source_item_id.encode()).hexdigest()[:10]


def _is_valid(listing: dict) -> bool:
    if listing.get("country") != "US":
        return False
    if not listing.get("main_image_id"):
        return False
    if not listing.get("brand"):
        return False
    if not _first_en_values(listing.get("item_name", [])):
        return False
    pt = listing.get("product_type")
    if not pt:
        return False
    return pt[0]["value"] in PRODUCT_TYPE_MAP


def iter_candidates() -> "list[Candidate]":
    out: dict[str, Candidate] = {}
    for listing in iter_all_raw_listings():
        if not _is_valid(listing):
            continue
        source_id = listing["item_id"]
        if source_id in out:
            continue
        product_type = listing["product_type"][0]["value"]
        type_info = PRODUCT_TYPE_MAP[product_type]
        raw_brand_values = [b.get("value", "") for b in listing.get("brand", [])]

        blob_parts = (
            _first_en_values(listing.get("item_name", []))
            + _first_en_values(listing.get("item_keywords", []))
            + _first_en_values(listing.get("bullet_point", []))
        )
        text_blob = " ".join(blob_parts).lower()

        if _BRANDING_RISK_KEYWORDS.search(text_blob):
            continue

        age_band = infer_age_band(type_info.age_band, text_blob)
        gender = infer_gender(type_info.gender, text_blob)

        out[source_id] = Candidate(
            item_id=_make_item_id(source_id),
            source_item_id=source_id,
            product_type=product_type,
            type_info=type_info,
            age_band=age_band,
            gender=gender,
            raw_brand_values=raw_brand_values,
            listing=listing,
            main_image_id=listing["main_image_id"],
            other_image_ids=listing.get("other_image_id", []) or [],
            text_blob=text_blob,
        )
    return list(out.values())
