"""server/catalog_store.py's rail_seasonal (close-out item 4) -- against
the real built catalog, skipped if it hasn't been built."""
import pytest

from server.catalog_store import get_store

try:
    get_store()
    _CATALOG_BUILT = True
except FileNotFoundError:
    _CATALOG_BUILT = False

pytestmark = pytest.mark.skipif(not _CATALOG_BUILT, reason="data/catalog.json not built — run `python -m catalog.build`")


def test_rail_seasonal_returns_empty_for_none():
    store = get_store()
    assert store.rail_seasonal("none") == []


def test_rail_seasonal_only_returns_items_tagged_with_that_season():
    store = get_store()
    for season in ("spring", "summer", "fall", "winter", "holiday"):
        items = store.rail_seasonal(season, limit=50)
        assert all(i["season"] == season for i in items)


def test_rail_seasonal_respects_limit():
    store = get_store()
    items = store.rail_seasonal("summer", limit=3)
    assert len(items) <= 3
