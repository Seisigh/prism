from catalog.brands import (
    assign_brand,
    brand_name_pool,
    contains_known_brand_string,
    strip_known_brand_strings,
)


def test_strip_known_brand_strings_removes_source_brand():
    text = "Amazon Brand - find. Women's Leather Loafer, Blue"
    out = strip_known_brand_strings(text, ["find.", "Amazon Brand - find."])
    assert "find" not in out.lower()
    assert "amazon" not in out.lower()


def test_strip_known_brand_strings_removes_denylisted_real_brands():
    text = "Works great with Nike shoes and an Apple charger"
    out = strip_known_brand_strings(text, [])
    assert "nike" not in out.lower()
    assert "apple" not in out.lower()


def test_strip_known_brand_strings_does_not_eat_unrelated_substrings():
    # "gap" is denylisted; must not eat "gaps" or "gaping" partial words
    # beyond the exact token, and must leave unrelated text intact.
    text = "Leaves no gaps between the panels"
    out = strip_known_brand_strings(text, [])
    assert "gaps" in out.lower()


def test_contains_known_brand_string_detects_whole_word_only():
    assert contains_known_brand_string("Made by Sony engineers", [])
    assert not contains_known_brand_string("A personal essay", [])  # no false hit on unrelated text


def test_assign_brand_is_deterministic():
    a = assign_brand("SOURCE123")
    b = assign_brand("SOURCE123")
    assert a == b


def test_assign_brand_varies_across_items():
    names = {assign_brand(f"item-{i}")["name"] for i in range(200)}
    assert len(names) > 20  # not collapsing onto one or two brands


def test_brand_pool_names_are_never_real_denylisted_brands():
    from catalog.brands import _DENYLIST

    pool = brand_name_pool(150)
    for entry in pool:
        assert entry["name"].lower() not in _DENYLIST
        assert entry["tier"] in ("value", "standard", "premium")
