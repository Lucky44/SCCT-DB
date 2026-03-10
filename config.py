import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_user_data_dir() -> str:
    """Return the platform-appropriate user data directory for SCCT."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.local/share")
    return os.path.join(base, "SCCT")


USER_DATA_DIR = get_user_data_dir()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "scct-local-app")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(USER_DATA_DIR, "scct.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    USER_DATA_DIR = USER_DATA_DIR
