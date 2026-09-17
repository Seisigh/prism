import random

from catalog.titles import generate_title, _looks_like_sku


def _listing(**overrides):
    base = {
        "brand": [{"language_tag": "en_US", "value": "Acme Corp"}],
        "color": [],
        "material": [],
        "style": [],
        "pattern": [],
        "item_keywords": [],
        "item_dimensions": {},
    }
    base.update(overrides)
    return base


def test_title_never_uses_source_brand():
    listing = _listing(
        material=[{"language_tag": "en_US", "value": "Acme Corp Premium Leather"}],
    )
    title = generate_title(listing, "SHOES", random.Random(1))
    assert "acme" not in title.lower()


def test_title_skips_sku_like_style_codes():
    listing = _listing(style=[{"language_tag": "en_US", "value": "Um1530"}])
    title = generate_title(listing, "SHOES", random.Random(1))
    assert "um1530" not in title.lower()


def test_looks_like_sku():
    assert _looks_like_sku("Um1530")
    assert _looks_like_sku("12-05-04")
    assert not _looks_like_sku("Tri-Ply Stainless")
    assert not _looks_like_sku("Oak")


def test_title_falls_back_to_keyword_when_no_descriptors():
    listing = _listing(item_keywords=[{"language_tag": "en_US", "value": "espresso maker"}])
    title = generate_title(listing, "KITCHEN", random.Random(1))
    assert title != "Kitchen Tool"
    assert "espresso" in title.lower() or "maker" in title.lower()


def test_title_includes_size_when_dimensions_present():
    listing = _listing(
        item_dimensions={"length": {"normalized_value": {"unit": "inches", "value": 3.0}}}
    )
    title = generate_title(listing, "TABLE", random.Random(1))
    assert "3in" in title
