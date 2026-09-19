"""In-memory catalog service backing the storefront API. Loads
data/catalog.json once at process start. No ranking model exists yet
(that's Gate 1) — "similar items" and recommendation rails here are
popularity/category heuristics, explicitly not presented as the real
recommender, and every rail response carries a `policy_id` so nothing
downstream can mistake this bootstrap ranking for a trained one.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from server.config import settings

PRICE_BANDS = [
    ("Under $25", 0, 2500),
    ("$25 to $50", 2500, 5000),
    ("$50 to $100", 5000, 10000),
    ("$100 to $250", 10000, 25000),
    ("Over $250", 25000, None),
]

_STOPWORDS = {"the", "a", "an", "for", "and", "of", "with", "in", "to"}


@dataclass
class SearchResult:
    items: list[dict]
    total: int
    facets: dict


class CatalogStore:
    def __init__(self, path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.context_items: list[dict] = raw["context_items"]
        self.core_items: list[dict] = raw["core_items"]
        self.all_items: list[dict] = self.context_items + self.core_items
        self.by_id: dict[str, dict] = {i["item_id"]: i for i in self.all_items}
        self.by_category: dict[str, list[dict]] = {}
        for item in self.all_items:
            self.by_category.setdefault(item["category"], []).append(item)
        self.categories: list[str] = sorted(self.by_category.keys())
        self.core_sets: dict[str, list[dict]] = {}
        for item in self.core_items:
            sid = item["near_substitute_set_id"]
            if sid:
                self.core_sets.setdefault(sid, []).append(item)
        self._search_index = self._build_search_index()

    def _build_search_index(self) -> dict[str, dict]:
        index: dict[str, dict] = {}
        for item in self.all_items:
            tokens = self._tokenize(f"{item['title']} {item['category']} {' '.join(item['verticals'])}")
            index[item["item_id"]] = tokens
        return index

    @staticmethod
    def _tokenize(text: str) -> dict[str, int]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        counts: dict[str, int] = {}
        for w in words:
            if w in _STOPWORDS or len(w) < 2:
                continue
            counts[w] = counts.get(w, 0) + 1
        return counts

    def get_item(self, item_id: str) -> dict | None:
        return self.by_id.get(item_id)

    def _score_score(self, item: dict) -> float:
        # Deterministic popularity proxy used only for non-personalized
        # fallback ordering (home rails before any session exists, search
        # relevance ties). Not a model; no impression is attributed to it
        # as anything other than `policy_id: "popularity_fallback"`.
        return item["rating"] * math.log(1 + item["review_count"])

    def _apply_filters(self, items: list[dict], filters: dict) -> list[dict]:
        out = items
        price_band = filters.get("price_band")
        if price_band:
            for label, lo, hi in PRICE_BANDS:
                if label == price_band:
                    out = [i for i in out if lo <= i["price_cents"] < (hi or 10**12)]
                    break
        min_rating = filters.get("min_rating")
        if min_rating:
            out = [i for i in out if i["rating"] >= float(min_rating)]
        gender = filters.get("gender")
        if gender:
            out = [i for i in out if i["gender"] == gender]
        in_stock_only = filters.get("in_stock_only")
        if in_stock_only:
            out = [i for i in out if i["stock_status"] != "out_of_stock"]
        return out

    def _facets(self, items: list[dict]) -> dict:
        price_band_counts = []
        for label, lo, hi in PRICE_BANDS:
            n = sum(1 for i in items if lo <= i["price_cents"] < (hi or 10**12))
            price_band_counts.append({"label": label, "count": n})
        rating_counts = [
            {"min_rating": r, "count": sum(1 for i in items if i["rating"] >= r)}
            for r in (4.5, 4.0, 3.0)
        ]
        return {"price_bands": price_band_counts, "ratings": rating_counts}

    def _sort(self, items: list[dict], sort: str | None) -> list[dict]:
        if sort == "price_asc":
            return sorted(items, key=lambda i: i["price_cents"])
        if sort == "price_desc":
            return sorted(items, key=lambda i: -i["price_cents"])
        if sort == "rating":
            return sorted(items, key=lambda i: (-i["rating"], -i["review_count"]))
        if sort == "newest":
            return list(reversed(items))
        return sorted(items, key=self._score_score, reverse=True)  # "featured" default

    def list_category(
        self, category: str, filters: dict, sort: str | None, page: int, page_size: int
    ) -> SearchResult:
        base = self.by_category.get(category, [])
        filtered = self._apply_filters(base, filters)
        ordered = self._sort(filtered, sort)
        start = (page - 1) * page_size
        return SearchResult(
            items=ordered[start : start + page_size], total=len(ordered), facets=self._facets(filtered)
        )

    def search(self, query: str, filters: dict, sort: str | None, page: int, page_size: int) -> SearchResult:
        q_tokens = list(self._tokenize(query).keys())
        scored = []
        for item in self.all_items:
            tokens = self._search_index[item["item_id"]]
            match = sum(tokens.get(t, 0) for t in q_tokens)
            partial = sum(
                1
                for t in q_tokens
                if any(t in existing for existing in tokens) and t not in tokens
            )
            score = match * 3 + partial
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: (-x[0], -self._score_score(x[1])))
        items = [i for _, i in scored]
        filtered = self._apply_filters(items, filters)
        if sort:
            ordered = self._sort(filtered, sort)
        else:
            ordered = filtered  # keep relevance order for default search sort
        start = (page - 1) * page_size
        return SearchResult(
            items=ordered[start : start + page_size], total=len(ordered), facets=self._facets(filtered)
        )

    def autocomplete(self, prefix: str, limit: int = 8) -> list[dict]:
        prefix = prefix.strip().lower()
        if not prefix:
            return []
        matches = [i for i in self.all_items if i["title"].lower().startswith(prefix)]
        if len(matches) < limit:
            contains = [
                i
                for i in self.all_items
                if prefix in i["title"].lower() and i not in matches
            ]
            matches += contains
        matches.sort(key=self._score_score, reverse=True)
        return [{"item_id": i["item_id"], "title": i["title"], "category": i["category"]} for i in matches[:limit]]

    def rail_popular_in_category(self, category: str, exclude_id: str | None, limit: int = 12) -> list[dict]:
        pool = [i for i in self.by_category.get(category, []) if i["item_id"] != exclude_id]
        pool.sort(key=self._score_score, reverse=True)
        return pool[:limit]

    def rail_seasonal(self, season: str, limit: int = 12) -> list[dict]:
        """Merchandising only (close-out item 4): items tagged with the
        given season, most-popular first. Empty list for "none" or a
        season with too few items to make a real rail -- the caller
        decides the minimum and whether to show the rail at all."""
        if season == "none":
            return []
        pool = [i for i in self.all_items if i.get("season") == season]
        pool.sort(key=self._score_score, reverse=True)
        return pool[:limit]

    def rail_similar_items(self, item: dict, limit: int = 12) -> list[dict]:
        pool = [
            i
            for i in self.by_category.get(item["category"], [])
            if i["item_id"] != item["item_id"]
        ]
        target = item["price_cents"]
        pool.sort(key=lambda i: (abs(i["price_cents"] - target), -self._score_score(i)))
        return pool[:limit]

    def compare_set(self, near_substitute_set_id: str) -> list[dict]:
        return self.core_sets.get(near_substitute_set_id, [])

    def home_categories(self, limit: int = 8) -> list[str]:
        return sorted(self.by_category.keys(), key=lambda c: -len(self.by_category[c]))[:limit]


@lru_cache(maxsize=1)
def get_store() -> CatalogStore:
    return CatalogStore(settings.catalog_path)
