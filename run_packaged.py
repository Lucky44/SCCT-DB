import threading
import webbrowser
from waitress import serve
from app import create_app

app = create_app()


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


threading.Timer(1.5, open_browser).start()
serve(app, host="127.0.0.1", port=5000)
