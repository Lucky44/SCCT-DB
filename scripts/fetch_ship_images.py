"""
Fetch ship images from FleetYards.net API and cache them locally.

Usage:
    venv/bin/python scripts/fetch_ship_images.py           # fetch all missing
    venv/bin/python scripts/fetch_ship_images.py --all     # re-fetch everything
    venv/bin/python scripts/fetch_ship_images.py --dry-run # show matches without downloading
"""

import os
import sys
import re
import time
import argparse
import urllib.request
from pathlib import Path

# Add project root to path so we can import Flask app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import Ship

FLEETYARDS_API = "https://api.fleetyards.net/v1"
RATE_LIMIT_DELAY = 0.3  # seconds between API calls

# Images go in user data dir so they survive app updates
from config import USER_DATA_DIR
IMAGES_DIR = Path(USER_DATA_DIR) / "images" / "ships"

# Use requests for HTTP
import requests
session = requests.Session()
session.headers.update({"User-Agent": "SCCT-DB/1.0"})


def strip_manufacturer(name: str) -> str:
    """Strip the first word (manufacturer prefix) from a ship name."""
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name


def search_fleetyards(query: str) -> list:
    """Query FleetYards search endpoint, return list of model results."""
    try:
        resp = session.get(
            f"{FLEETYARDS_API}/models",
            params={"q[name_cont]": query, "per_page": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"    API error for '{query}': {e}")
        return []


def best_match(results: list, query: str) -> dict | None:
    """Pick the best matching result from a list, preferring exact name matches."""
    if not results:
        return None
    query_lower = query.lower()
    # Prefer exact name match
    for r in results:
        if r.get("name", "").lower() == query_lower:
            return r
    # Accept first result if only one
    if len(results) == 1:
        return results[0]
    # Prefer result whose name contains the full query
    for r in results:
        if query_lower in r.get("name", "").lower():
            return r
    return results[0]


def find_fleetyards_model(ship: Ship) -> dict | None:
    """
    Try multiple strategies to find a FleetYards model for a ship.
    Returns the matched model dict or None.
    """
    model_name = strip_manufacturer(ship.name)

    # Strategy 1: model name without manufacturer prefix
    results = search_fleetyards(model_name)
    match = best_match(results, model_name)
    if match:
        return match

    time.sleep(RATE_LIMIT_DELAY)

    # Strategy 2: full name including manufacturer
    results = search_fleetyards(ship.name)
    match = best_match(results, ship.name)
    if match:
        return match

    time.sleep(RATE_LIMIT_DELAY)

    # Strategy 3: try significant words from the model name (skip short words)
    words = [w for w in model_name.split() if len(w) > 2]
    for word in words:
        results = search_fleetyards(word)
        match = best_match(results, word)
        if match:
            return match
        time.sleep(RATE_LIMIT_DELAY)

    return None


def pick_image_url(model: dict, size: str = "medium") -> str | None:
    """Pick the best image URL from a FleetYards model result.

    The API returns flat keys like angledViewMedium, storeImageMedium, etc.
    """
    size_cap = size.capitalize()  # "medium" -> "Medium"
    # Prefer angledView, fall back to storeImage
    for prefix in ("angledView", "storeImage"):
        url = model.get(f"{prefix}{size_cap}") or model.get(prefix)
        if url:
            return url
    return None


def safe_filename(ship: Ship) -> str:
    """Generate a safe filename from ship name."""
    name = re.sub(r"[^a-z0-9_-]", "_", ship.name.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return f"{name}.jpg"


def download_image(url: str, dest: Path) -> bool:
    """Download an image URL to dest path. Returns True on success."""
    try:
        resp = session.get(url, timeout=15, stream=True)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


def fetch_images(force_all: bool = False, dry_run: bool = False):
    app = create_app()
    with app.app_context():
        ships = Ship.query.order_by(Ship.name).all()
        print(f"Processing {len(ships)} ships...\n")

        matched = []
        unmatched = []

        for ship in ships:
            # Skip if already cached (unless --all)
            if not force_all and ship.image_path:
                img_file = Path(__file__).parent.parent / "app" / "static" / ship.image_path
                if img_file.exists():
                    print(f"  [skip] {ship.name} (cached)")
                    continue

            print(f"  Searching: {ship.name}")
            model = find_fleetyards_model(ship)

            if not model:
                print(f"    [UNMATCHED] {ship.name}")
                unmatched.append(ship.name)
                continue

            fy_name = model.get("name", "?")
            sc_id = model.get("scIdentifier", "?")
            print(f"    Matched → '{fy_name}' (sc_id: {sc_id})")
            matched.append((ship.name, fy_name))

            if dry_run:
                continue

            # Pick medium for hangar cards; also grab large for detail page
            # We just save one file per ship (medium works fine for both with CSS)
            url = pick_image_url(model, "medium")
            if not url:
                url = pick_image_url(model, "large")
            if not url:
                print(f"    No image URL in response")
                unmatched.append(ship.name)
                continue

            filename = safe_filename(ship)
            dest = IMAGES_DIR / filename
            print(f"    Downloading {url}")

            if download_image(url, dest):
                rel_path = f"images/ships/{filename}"
                ship.image_path = rel_path
                db.session.commit()
                print(f"    Saved → {rel_path}")
            else:
                unmatched.append(ship.name)

            time.sleep(RATE_LIMIT_DELAY)

        print(f"\n{'='*60}")
        print(f"Done. Matched: {len(matched)}, Unmatched: {len(unmatched)}")
        if unmatched:
            print("\nUnmatched ships (need manual fix):")
            for name in unmatched:
                print(f"  - {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ship images from FleetYards.net")
    parser.add_argument("--all", action="store_true", dest="force_all",
                        help="Re-fetch images even if already cached")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show API matches without downloading anything")
    args = parser.parse_args()
    fetch_images(force_all=args.force_all, dry_run=args.dry_run)
