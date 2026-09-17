"""Fetch Amazon Berkeley Objects (ABO) source data.

Downloads are cached under data/raw/ (gitignored — see .gitignore). This
module never writes anything under data/images or data/thumbs; that is
images.py's job, run at catalog build time per BUILD_BRIEF.md §5.5.
"""
from __future__ import annotations

import gzip
import json
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx

BUCKET = "https://amazon-berkeley-objects.s3.amazonaws.com"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
SHARD_IDS = list("0123456789abcdef")

# catalog/build.py fetches per-item images from a thread pool (§5.5), and
# every one of those threads calls fetch_images_index() the first time it
# needs the shared image path index. Without a lock, two threads racing
# on a cold cache both see the destination missing, both download to the
# same .part path, and the loser's rename fails with "no such file" once
# the winner has already moved it — observed for real the first time this
# ran against a completely empty cache (a fresh Docker build), not just a
# theoretical race. A per-destination lock (keyed by the final path, so
# unrelated downloads never block each other) fixes it at the root rather
# than special-casing the one caller that happened to trigger it.
_download_locks: dict[Path, threading.Lock] = {}
_download_locks_guard = threading.Lock()


def _lock_for(dest: Path) -> threading.Lock:
    with _download_locks_guard:
        return _download_locks.setdefault(dest, threading.Lock())


def _download(url: str, dest: Path) -> Path:
    with _lock_for(dest):
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        # A uuid-suffixed temp name, not a fixed `.part`, so even an
        # out-of-process concurrent run (e.g. a second `catalog.build`
        # invocation) can't collide on the same temp file.
        tmp = dest.with_suffix(dest.suffix + f".{uuid.uuid4().hex[:8]}.part")
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1 << 16):
                    f.write(chunk)
        tmp.rename(dest)
        return dest


def fetch_listings_shard(shard_id: str) -> Path:
    """Download one of the 16 listings_*.json.gz metadata shards."""
    dest = RAW_DIR / f"listings_{shard_id}.json.gz"
    return _download(f"{BUCKET}/listings/metadata/listings_{shard_id}.json.gz", dest)


def fetch_all_listing_shards() -> list[Path]:
    return [fetch_listings_shard(s) for s in SHARD_IDS]


def fetch_images_index() -> Path:
    """Download images/metadata/images.csv.gz: image_id -> path/height/width."""
    dest = RAW_DIR / "images.csv.gz"
    return _download(f"{BUCKET}/images/metadata/images.csv.gz", dest)


def fetch_small_image(relative_path: str) -> bytes:
    """Fetch one image from images/small/<relative_path>. Not cached to disk
    here; the caller (images.py) decides thumbnail placement."""
    url = f"{BUCKET}/images/small/{relative_path}"
    r = httpx.get(url, timeout=30.0)
    r.raise_for_status()
    return r.content


def iter_raw_listings(shard_path: Path) -> Iterator[dict]:
    with gzip.open(shard_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_all_raw_listings() -> Iterator[dict]:
    for shard_id in SHARD_IDS:
        path = fetch_listings_shard(shard_id)
        yield from iter_raw_listings(path)


if __name__ == "__main__":
    print("Fetching 16 ABO listing shards + image index (cached in data/raw/)...")
    fetch_all_listing_shards()
    fetch_images_index()
    print("Done.")
