"""Build-failing integration check over the real generated catalog:
non-negotiable #2 says no real brand name in any served text. This scans
every served text field of the actual catalog.json output, not just the
unit-level scrubbing functions, so a gap in wiring (a field that forgot to
call strip_known_brand_strings) gets caught here even if the individual
functions are individually correct.
"""
import json

import pytest

from catalog.brands import contains_known_brand_string
from catalog.build import OUT_PATH

pytestmark = pytest.mark.skipif(not OUT_PATH.exists(), reason="catalog not built yet — run `python -m catalog.build`")


def _served_text_fields(item: dict) -> list[str]:
    fields = [item["title"], item["description"], item["brand"]]
    fields += item["bullets"]
    fields += list(item["spec"].values())
    return fields


def test_no_real_brand_strings_in_served_catalog_text():
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    violations = []
    for item in data["context_items"] + data["core_items"]:
        for field_value in _served_text_fields(item):
            if contains_known_brand_string(field_value, []):
                violations.append((item["item_id"], field_value))
    assert not violations, f"real brand strings leaked into served text: {violations[:20]}"
