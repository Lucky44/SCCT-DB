"""
Fetch ships.json and ship-items.json from StarCitizenWiki/scunpacked-data on GitHub
and save them to data/.

This script replaces fetch_erkul_data.py in the automated update pipeline:
  1. Run this script to check/pull fresh data from scunpacked-data
  2. Run import_scunpacked.py to import into the DB
  3. GitHub Actions runs both on a schedule and builds a new exe if data changed

Change detection is done via the latest commit SHA - no need to download the full
files just to check whether anything changed.

Usage:
    python scripts/fetch_scunpacked_data.py [--check-only]

Options:
    --check-only  Exit 0 if data unchanged, exit 1 if changed (used by CI)

Environment:
    GITHUB_TOKEN  Optional. Set to a GitHub PAT or Actions token to raise the
                  API rate limit from 60 to 5000 req/hour.
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

REPO   = "StarCitizenWiki/scunpacked-data"
BRANCH = "master"

GITHUB_API_COMMIT = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
BASE_RAW          = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

FILES = ["ships.json", "ship-items.json"]

METADATA_FILE = os.path.join(DATA_DIR, "scunpacked_meta.json")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    h = {"User-Agent": "SCCT-DataFetcher/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_latest_sha() -> str:
    """Return the latest commit SHA on BRANCH."""
    req = urllib.request.Request(GITHUB_API_COMMIT, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["sha"]


def download_file(filename: str, log=print) -> None:
    dest = os.path.join(DATA_DIR, filename)
    url  = f"{BASE_RAW}/{filename}"
    log(f"  Downloading {filename} ...")
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
    log(f"    -> {os.path.getsize(dest) // 1024} KB saved to {dest}")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def load_meta() -> dict:
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(sha: str) -> None:
    meta = {
        "commit_sha": sha,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     f"https://github.com/{REPO}/commit/{sha}",
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(check_only: bool = False, log=print) -> bool:
    """
    Check for new scunpacked data and optionally download it.
    Returns True if data changed (or would change).
    """
    log(f"Checking {REPO} for updates ...")

    try:
        latest_sha = get_latest_sha()
    except Exception as exc:
        log(f"ERROR: could not reach GitHub API: {exc}", file=sys.stderr)
        sys.exit(1)

    meta      = load_meta()
    known_sha = meta.get("commit_sha", "")
    changed   = (latest_sha != known_sha)

    log(f"  Remote commit: {latest_sha[:16]}...")
    log(f"  Local commit:  {known_sha[:16] if known_sha else '(none)'}...")
    log(f"  Status: {'CHANGED' if changed else 'UNCHANGED'}")

    if check_only or not changed:
        return changed

    os.makedirs(DATA_DIR, exist_ok=True)
    for filename in FILES:
        download_file(filename, log=log)

    save_meta(latest_sha)

    log(f"\n=== scunpacked fetch complete ===")
    log(f"  Commit: {latest_sha[:16]}...")
    log(f"  Files:  {', '.join(FILES)}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch scunpacked game data from GitHub")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 1 if new data available, 0 if unchanged (no download)",
    )
    args = parser.parse_args()

    changed = run(check_only=args.check_only)

    if args.check_only:
        sys.exit(1 if changed else 0)
