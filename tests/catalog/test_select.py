from catalog.candidates import Candidate
from catalog.select import _spec_table


def _candidate(**listing_overrides):
    listing = {
        "material": [{"language_tag": "en_US", "value": "spun_polyester"}],
    }
    listing.update(listing_overrides)
    return Candidate(
        item_id="p-test",
        source_item_id="src-test",
        product_type="PILLOW",
        type_info=None,
        age_band="unisex",
        gender="unisex",
        raw_brand_values=[],
        listing=listing,
        main_image_id="img-1",
        other_image_ids=[],
        text_blob="",
    )


def test_spec_table_never_leaks_a_raw_snake_case_attribute():
    spec = _spec_table(_candidate(), brand="Acme")
    assert "_" not in spec["Material"]
    assert spec["Material"] == "spun polyester"
