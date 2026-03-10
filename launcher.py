"""
SCCT Launcher — entry point for the packaged desktop app.

Handles first-run setup (DB init, game data import, image fetch),
starts the Flask server, and opens the browser automatically.
"""

import os
import sys
import threading
import webbrowser
import time

# When frozen by PyInstaller, sys._MEIPASS is the temp folder with bundled files.
# We add it to sys.path so all app imports work the same as in dev.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

from config import USER_DATA_DIR
from app import create_app, db


def setup_dirs():
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(USER_DATA_DIR, "images", "ships"), exist_ok=True)


def run_migrations(app):
    """Create all DB tables. For packaged app, create_all is sufficient."""
    with app.app_context():
        db.create_all()


def import_game_data(app):
    """Import ships/components/weapons if the DB is empty."""
    from app.models import Ship
    with app.app_context():
        if Ship.query.count() > 0:
            return
        print("First run: importing game data...")
        scripts_dir = os.path.join(BASE_DIR, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from import_scunpacked import do_import, DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON
        do_import(DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON)
        print("Game data imported.")


def fetch_images(app):
    """Fetch ship images if they haven't been downloaded yet."""
    images_dir = os.path.join(USER_DATA_DIR, "images", "ships")
    if os.listdir(images_dir):
        return  # already have images
    print("First run: fetching ship images (this may take a minute)...")
    scripts_dir = os.path.join(BASE_DIR, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from fetch_ship_images import fetch_images as _fetch
    _fetch()
    print("Ship images downloaded.")


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")


def main():
    setup_dirs()

    app = create_app()
    run_migrations(app)
    import_game_data(app)
    fetch_images(app)

    threading.Thread(target=open_browser, daemon=True).start()

    print("Starting SCCT at http://127.0.0.1:5000 — close this window to quit.")
    app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)


if __name__ == "__main__":
    main()
