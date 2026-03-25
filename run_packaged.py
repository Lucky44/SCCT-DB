import threading
import webbrowser
from waitress import serve
from app import create_app
from app.updater import check_for_update

app = create_app()


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


threading.Thread(target=check_for_update, daemon=True).start()
threading.Timer(1.5, open_browser).start()
serve(app, host="127.0.0.1", port=5000)
