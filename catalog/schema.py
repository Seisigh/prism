"""The served catalog item shape. One dataclass, one source of truth,
serialized to JSON for both the storefront and Postgres seeding."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

Gender = Literal["womens", "mens", "unisex"]
AgeBand = Literal["kids", "teen", "adult", "older_adult"]
StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]
Season = Literal["spring", "summer", "fall", "winter", "holiday", "none"]
DescriptionBand = Literal["short", "medium", "long"]
CopyFraming = Literal["feature_led", "benefit_led"]
BrandTier = Literal["value", "standard", "premium"]


@dataclass
class ImageSet:
    grid: str
    detail: str
    zoom: str
    detail_gallery: list[str] = field(default_factory=list)  # additional detail-page images


@dataclass
class ReviewSnippet:
    stars: int
    body: str
    synthetic: bool


@dataclass
class CatalogItem:
    item_id: str
    title: str
    category: str
    verticals: list[str]
    gender: Gender
    age_band: AgeBand
    brand: str
    brand_tier: BrandTier
    description: str
    description_band: DescriptionBand
    copy_framing: CopyFraming
    bullets: list[str]
    spec: dict[str, str]
    price_cents: int
    anchor_price_cents: int | None
    rating: float
    review_count: int
    stock_status: StockStatus
    stock_label: str | None
    shipping_line: str
    images: ImageSet | None
    is_core: bool
    near_substitute_set_id: str | None
    varied_attribute: str | None
    badges: list[str]
    alt_text: str
    reviews: list[ReviewSnippet]
    # Merchandising only (close-out item 4) -- which rail surfaces this
    # item and whether it gets a seasonal badge. Never read by
    # server/features/, sim/, or eval/ -- see catalog/synth_attributes.py's
    # generate_season docstring.
    season: Season
    # internal provenance, not served to the client but kept for pipeline debugging
    _source_item_id: str = ""
    _product_type: str = ""

    def to_public_dict(self) -> dict:
        d = asdict(self)
        d.pop("_source_item_id", None)
        d.pop("_product_type", None)
        return d
