import os
import threading
import webbrowser
from waitress import serve
from config import USER_DATA_DIR
from app import create_app
from app.updater import check_for_update

# Ensure the user data directory exists before anything opens the database.
# SQLite creates the .db file but not missing parent folders, so on a fresh
# machine create_app()'s db.create_all() would fail with "unable to open
# database file". (launcher.py does this via setup_dirs(); the packaged exe
# uses this entry point instead, so it must do it too.)
os.makedirs(os.path.join(USER_DATA_DIR, "images", "ships"), exist_ok=True)

app = create_app()


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


threading.Thread(target=check_for_update, daemon=True).start()
threading.Timer(1.5, open_browser).start()
serve(app, host="127.0.0.1", port=5000)
