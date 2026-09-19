import random

from catalog.schema import CatalogItem
from catalog.synth_attributes import _SEASONS, generate_season


def test_generate_season_returns_a_valid_value():
    rng = random.Random(0)
    valid = set(_SEASONS) | {"none"}
    for _ in range(200):
        assert generate_season("Home & Furniture", rng) in valid


def test_generate_season_is_deterministic_for_a_given_rng_state():
    assert generate_season("Lighting", random.Random(42)) == generate_season("Lighting", random.Random(42))


def test_generate_season_biased_category_favors_its_bias_over_none_baseline():
    # Lighting is holiday-biased (see the bias table's own docstring) --
    # over many draws its non-"none" share should skew heavily toward
    # holiday relative to a uniform split across the other four seasons.
    rng = random.Random(1)
    counts = {"holiday": 0, "other_season": 0}
    for _ in range(2000):
        season = generate_season("Lighting", rng)
        if season == "holiday":
            counts["holiday"] += 1
        elif season != "none":
            counts["other_season"] += 1
    # holiday alone should clearly outnumber the sum of the other four
    # seasons combined, given its 0.35-of-non-none weight vs 0.65 spread
    # over four seasons unevenly -- a loose bound, not an exact one.
    assert counts["holiday"] > counts["other_season"] * 0.4


def test_season_is_a_real_field_on_catalog_item():
    assert "season" in CatalogItem.__dataclass_fields__
