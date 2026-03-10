import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

    @app.template_filter("ship_model")
    def ship_model_filter(name):
        """Strip the manufacturer abbreviation prefix (first word) from a ship name."""
        parts = name.split(" ", 1)
        return parts[1] if len(parts) > 1 else name

    return app
