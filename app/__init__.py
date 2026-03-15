import os
import re
import shutil
import unicodedata
from datetime import datetime
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


def backup_database(user_data_dir):
    db_path = os.path.join(user_data_dir, "scct.db")
    if not os.path.exists(db_path) or os.path.getsize(db_path) < 4096:
        return
    backup_dir = os.path.join(user_data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy2(db_path, os.path.join(backup_dir, f"scct_backup_{timestamp}.db"))
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("scct_backup_")],
        reverse=True
    )
    for old in backups[10:]:
        os.remove(os.path.join(backup_dir, old))

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object("config.Config")

    # Serve ship images from the user data directory (works both in dev and packaged)
    @app.route("/user-static/<path:filename>")
    def user_static(filename):
        from config import USER_DATA_DIR
        return send_from_directory(USER_DATA_DIR, filename)

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from app import models  # noqa: F401 — ensures models are registered

        from app.routes.dashboard import dashboard_bp
        from app.routes.my_ships import my_ships_bp
        from app.routes.in_storage import in_storage_bp
        from app.routes.browser import browser_bp
        from app.routes.api import api_bp

        app.register_blueprint(dashboard_bp)
        app.register_blueprint(my_ships_bp)
        app.register_blueprint(in_storage_bp)
        app.register_blueprint(browser_bp)
        app.register_blueprint(api_bp)

        db.create_all()
        backup_database(app.config["USER_DATA_DIR"])

    @app.template_filter("ship_model")
    def ship_model_filter(name):
        """Strip the manufacturer abbreviation prefix (first word) from a ship name."""
        parts = name.split(" ", 1)
        return parts[1] if len(parts) > 1 else name

    @app.template_filter("ship_image")
    def ship_image_filter(name):
        """Derive the static image path from a ship name."""
        # Strip accents (ā→a, ī→i, etc.) — but handle ī specially before stripping
        s = name.replace('yāi', 'y_i')  # San'tok.yāi edge case
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
        s = s.lower()
        s = re.sub(r'[^a-z0-9\-]+', '_', s)  # non-alphanum/hyphen → underscore
        s = re.sub(r'_+', '_', s).strip('_')
        return f'images/ships/{s}.jpg'

    return app
