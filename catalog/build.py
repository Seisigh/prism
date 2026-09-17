"""Catalog build CLI: selection -> generation -> images -> catalog.json.

Run with: .venv/Scripts/python.exe -m catalog.build
Output: data/catalog.json (gitignored — see .gitignore's data/ rules;
this file is a build artifact, the server seeds Postgres from it, and
`server/ingest`'s tests use small hand-built fixtures instead of depending
on a live catalog build).
"""
from __future__ import annotations

import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from catalog.images import build_thumbnails_for_item
from catalog.schema import CatalogItem, ImageSet
from catalog.select import _GALLERY_RAMP, build_catalog

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
DEFAULT_GALLERY_SIZE = 3


def _gallery_size_for(item: CatalogItem, set_index_by_item: dict[str, int]) -> int:
    if item.is_core and item.varied_attribute == "gallery_size":
        idx = set_index_by_item[item.item_id]
        return _GALLERY_RAMP[idx]
    rng = random.Random(item.item_id)
    return rng.choice([2, 3, 3, 4])


def main() -> None:
    t0 = time.time()
    print("Selecting candidates and generating attributes...")
    result = build_catalog()
    context_items: list[CatalogItem] = result["context_items"]
    core_items: list[CatalogItem] = result["core_items"]
    all_items = context_items + core_items
    print(f"  context={len(context_items)} core={len(core_items)} ({time.time()-t0:.1f}s)")

    set_index_by_item: dict[str, int] = {}
    for _set_id, _varied, item_ids in result["core_sets"]:
        for i, item_id in enumerate(item_ids):
            set_index_by_item[item_id] = i

    # We need the raw candidate's main/other image ids, which select.py
    # doesn't carry on CatalogItem (it's a served shape). Re-derive via a
    # side table built during the same candidate pass, keyed by item_id.
    from catalog.candidates import iter_candidates

    candidates_by_id = {c.item_id: c for c in iter_candidates()}

    print(f"Fetching + resizing images for {len(all_items)} items (parallel)...")

    def process(item: CatalogItem) -> tuple[str, dict]:
        cand = candidates_by_id[item.item_id]
        gallery_size = _gallery_size_for(item, set_index_by_item)
        images = build_thumbnails_for_item(
            item.item_id, cand.main_image_id, cand.other_image_ids, gallery_size
        )
        return item.item_id, images

    images_by_id: dict[str, dict] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(process, item): item for item in all_items}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                item_id, images = fut.result()
                images_by_id[item_id] = images
            except Exception as e:
                print(f"  ! image build failed for {item.item_id}: {e}", file=sys.stderr)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(all_items)} ({time.time()-t0:.1f}s)")

    for item in all_items:
        images = images_by_id.get(item.item_id)
        if images and images["grid"]:
            item.images = ImageSet(
                grid=images["grid"],
                detail=images["detail"],
                zoom=images["zoom"],
                detail_gallery=images["detail_gallery"],
            )

    before = len(all_items)
    context_items = [i for i in context_items if i.images is not None]
    core_items = [i for i in core_items if i.images is not None]
    dropped = before - len(context_items) - len(core_items)
    if dropped:
        print(f"  dropped {dropped} items with no resolvable image")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "context_items": [i.to_public_dict() for i in context_items],
        "core_items": [i.to_public_dict() for i in core_items],
    }
    OUT_PATH.write_text(json.dumps(payload, indent=None), encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({time.time()-t0:.1f}s total)")
    print(f"  context={len(context_items)} core={len(core_items)}")


if __name__ == "__main__":
    main()
