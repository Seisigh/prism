"""server/recommender/catalog_view.py: catalog loading joined with
sim/embedding.py's vectors, and category/price-band filtering."""
import pytest

from server.recommender.catalog_view import filter_candidates, load_catalog_items, price_band_index
from sim.embedding import build_item_vectors

try:
    build_item_vectors()
    _CATALOG_BUILT = True
except FileNotFoundError:
    _CATALOG_BUILT = False

pytestmark = pytest.mark.skipif(not _CATALOG_BUILT, reason="data/catalog.json not built — run `python -m catalog.build`")


def test_price_band_index_boundaries():
    assert price_band_index(0) == 0
    assert price_band_index(2499) == 0
    assert price_band_index(2500) == 1
    assert price_band_index(10**9) == 4  # far past the top band


def test_load_catalog_items_context_only_by_default():
    items = load_catalog_items()
    assert len(items) > 0
    for item in items.values():
        assert len(item.vector) == 7  # sim/embedding.py's DIMENSIONS


def test_filter_candidates_by_category():
    items = load_catalog_items()
    category = next(iter(items.values())).category
    filtered = filter_candidates(items, category=category)
    assert filtered
    assert all(item.category == category for item in filtered.values())


def test_filter_candidates_excludes_given_item_ids():
    items = load_catalog_items()
    some_id = next(iter(items.keys()))
    filtered = filter_candidates(items, exclude_item_ids=frozenset({some_id}))
    assert some_id not in filtered
