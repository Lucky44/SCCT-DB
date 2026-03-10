"""
Pre-build step: copies ships.json and ship-items.json into data/
so PyInstaller can bundle them.

Run this before building:
    python prepare_build.py
"""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = PROJECT_ROOT / ".." / "SC-Component-Tracker"

FILES = ["ships.json", "ship-items.json"]

DATA_DIR.mkdir(exist_ok=True)

for fname in FILES:
    src = SOURCE_DIR / fname
    dst = DATA_DIR / fname
    if not src.exists():
        print(f"ERROR: {src} not found — check the SC-Component-Tracker path")
        raise SystemExit(1)
    shutil.copy2(src, dst)
    print(f"Copied {fname} → data/{fname}")

print("Done. Ready to run PyInstaller.")
