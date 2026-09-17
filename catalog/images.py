"""Fetches source imagery for selected catalog items and resizes to the
grid/detail/zoom thumbnail set at build time (§5.5).

Main image comes from images/original/ (so the detail/zoom crops have
real resolution to work with); gallery images come from images/small/
(they're navigation thumbnails, not the zoom target). Both are ABO paths,
looked up via images.csv.gz. Nothing here is committed — see .gitignore.
"""
from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

from PIL import Image

from catalog.download import BUCKET, RAW_DIR, fetch_images_index, fetch_small_image
import httpx

THUMBS_DIR = Path(__file__).resolve().parent.parent / "data" / "thumbs"

SIZES = {
    "grid": (480, 480),
    "detail": (900, 900),
    "zoom": (1800, 1800),
}
GALLERY_SIZE = (480, 480)

_index_cache: dict[str, str] | None = None


def _load_index() -> dict[str, str]:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    path = fetch_images_index()
    idx: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            idx[row["image_id"]] = row["path"]
    _index_cache = idx
    return idx


def _fetch_original(relative_path: str) -> bytes:
    url = f"{BUCKET}/images/original/{relative_path}"
    r = httpx.get(url, timeout=30.0)
    r.raise_for_status()
    return r.content


_CANVAS_RGB = (255, 255, 255)  # matches --surface token; product never crops


def _resize_contain(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Fit the whole product inside a fixed-aspect canvas, never cropping
    it — a tall narrow product (a glass, a bottle) shouldn't lose its top
    and bottom to a cover-crop. Pads with the storefront's white surface
    color so grid/detail/zoom containers stay a fixed aspect ratio."""
    im = im.convert("RGB")
    target_w, target_h = size
    src_w, src_h = im.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", size, _CANVAS_RGB)
    canvas.paste(im, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def _save_webp(im: Image.Image, dest: Path, quality: int = 82) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=quality, method=5)


def build_thumbnails_for_item(item_id: str, main_image_id: str, other_image_ids: list[str], gallery_size: int) -> dict:
    """Downloads + resizes; returns paths relative to data/thumbs/ (which
    the server serves statically). Idempotent: skips work already done."""
    index = _load_index()
    item_dir = THUMBS_DIR / item_id
    result = {"grid": None, "detail": None, "zoom": None, "detail_gallery": []}

    main_path = index.get(main_image_id)
    if main_path is None:
        return result

    grid_dest = item_dir / "grid.webp"
    detail_dest = item_dir / "detail.webp"
    zoom_dest = item_dir / "zoom.webp"
    need_main = not (grid_dest.exists() and detail_dest.exists() and zoom_dest.exists())
    if need_main:
        raw = _fetch_original(main_path)
        im = Image.open(io.BytesIO(raw))
        _save_webp(_resize_contain(im, SIZES["grid"]), grid_dest)
        _save_webp(_resize_contain(im, SIZES["detail"]), detail_dest)
        im.convert("RGB")
        zoom_im = im.copy()
        zoom_im.thumbnail(SIZES["zoom"], Image.LANCZOS)
        _save_webp(zoom_im, zoom_dest)

    result["grid"] = f"{item_id}/grid.webp"
    result["detail"] = f"{item_id}/detail.webp"
    result["zoom"] = f"{item_id}/zoom.webp"

    n_gallery = max(0, gallery_size - 1)  # main image already counts as slot 1
    for i, image_id in enumerate(other_image_ids[:n_gallery]):
        dest = item_dir / f"gallery-{i}.webp"
        if not dest.exists():
            gpath = index.get(image_id)
            if gpath is None:
                continue
            try:
                raw = fetch_small_image(gpath)
            except httpx.HTTPStatusError:
                continue
            im = Image.open(io.BytesIO(raw))
            _save_webp(_resize_contain(im, GALLERY_SIZE), dest)
        result["detail_gallery"].append(f"{item_id}/gallery-{i}.webp")

    return result
