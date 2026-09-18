"""PRISM FastAPI app: catalog browsing API + static thumbnail serving.

Telemetry ingest (WebSocket + HTTP) lives in server/ingest and is wired in
here once that module exists (see STATE.md — next module in the build
order). This file intentionally stays a single FastAPI app per §2:
"One FastAPI app, one React app."
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.catalog_store import get_store
from server.config import settings
from server.ingest.admin_routes import router as admin_router
from server.ingest.routes import router as ingest_router

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI(title="PRISM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def noindex_header(request, call_next):
    # Non-negotiable #4: robots noindex on every response, defense in
    # depth alongside the HTML <meta name="robots"> tag the SPA renders.
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


settings.thumbs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/thumbs", StaticFiles(directory=str(settings.thumbs_dir)), name="thumbs")

app.include_router(ingest_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/categories")
def categories():
    store = get_store()
    return {"categories": store.categories}


@app.get("/api/brand-tokens")
def brand_tokens():
    """The closed set of invented-brand tokens actually in the catalog —
    the SDK's online mode classifier (§4.1's "invented-brand token" rule)
    needs this set to recognize a directed-search query without shipping
    a full brand list of its own."""
    store = get_store()
    tokens: set[str] = set()
    for item in store.all_items:
        tokens.update(item["brand"].lower().replace("&", " ").split())
    tokens.discard("co.")
    return {"tokens": sorted(tokens)}


@app.get("/api/items/{item_id}")
def get_item(item_id: str):
    store = get_store()
    item = store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@app.get("/api/items/{item_id}/similar")
def similar_items(item_id: str, limit: int = 12):
    store = get_store()
    item = store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return {
        "rail_id": f"similar-{item_id}",
        "policy_id": "category_price_proximity_fallback",
        "items": store.rail_similar_items(item, limit=limit),
    }


@app.get("/api/items/{item_id}/also-viewed")
def also_viewed(item_id: str, limit: int = 12):
    store = get_store()
    item = store.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return {
        "rail_id": f"also-viewed-{item_id}",
        "policy_id": "popularity_fallback",
        "items": store.rail_popular_in_category(item["category"], exclude_id=item_id, limit=limit),
    }


@app.get("/api/compare/{set_id}")
def compare(set_id: str):
    store = get_store()
    items = store.compare_set(set_id)
    if not items:
        raise HTTPException(status_code=404, detail="comparison set not found")
    return {"near_substitute_set_id": set_id, "items": items}


def _parse_filters(price_band: str | None, min_rating: float | None, gender: str | None, in_stock_only: bool) -> dict:
    return {
        "price_band": price_band,
        "min_rating": min_rating,
        "gender": gender,
        "in_stock_only": in_stock_only or None,
    }


@app.get("/api/category/{category}")
def category_page(
    category: str,
    price_band: str | None = None,
    min_rating: float | None = None,
    gender: str | None = None,
    in_stock_only: bool = False,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=96),
):
    store = get_store()
    if category not in store.categories:
        raise HTTPException(status_code=404, detail="category not found")
    result = store.list_category(
        category, _parse_filters(price_band, min_rating, gender, in_stock_only), sort, page, page_size
    )
    return {"items": result.items, "total": result.total, "facets": result.facets, "page": page, "page_size": page_size}


@app.get("/api/search")
def search(
    q: str = "",
    price_band: str | None = None,
    min_rating: float | None = None,
    gender: str | None = None,
    in_stock_only: bool = False,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=96),
):
    store = get_store()
    result = store.search(
        q, _parse_filters(price_band, min_rating, gender, in_stock_only), sort, page, page_size
    )
    return {
        "query": q,
        "items": result.items,
        "total": result.total,
        "facets": result.facets,
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/autocomplete")
def autocomplete(q: str = ""):
    store = get_store()
    return {"suggestions": store.autocomplete(q)}


@app.get("/api/home")
def home():
    store = get_store()
    top_categories = store.home_categories(limit=8)
    rails = []
    for cat in top_categories[:4]:
        items = store.rail_popular_in_category(cat, exclude_id=None, limit=12)
        rails.append({"rail_id": f"home-{cat}", "policy_id": "popularity_fallback", "title": cat, "items": items})
    return {"categories": store.categories, "rails": rails}


# Production only: serve the built React app from the same process (§2's
# "one FastAPI app, one React app" — in prod that's one process too). In
# dev, Vite's own server handles this and proxies /api and /ws here
# instead (see web/vite.config.ts); web/dist doesn't exist in dev.
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="web-assets")

    @app.get("/{full_path:path}")
    @app.head("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Any path not already matched by an API route above is a
        # client-side route (react-router) — serve index.html and let
        # the SPA's own router take it from there.
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
