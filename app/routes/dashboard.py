import os
import sys
from flask import Blueprint, render_template, redirect, url_for, flash
from app import db
from app.models import Ship, Component, Weapon, MyShip, MyInventory

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    stats = {
        "total_ships_ref": db.session.query(Ship).count(),
        "total_components_ref": db.session.query(Component).count(),
        "total_weapons_ref": db.session.query(Weapon).count(),
        "my_ship_count": db.session.query(MyShip).count(),
        "my_inventory_count": db.session.query(MyInventory).count(),
    }
    return render_template("dashboard.html", stats=stats)


@dashboard_bp.route("/update-game-data", methods=["POST"])
def update_game_data():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scripts_dir = os.path.join(project_root, "scripts")
    sys.path.insert(0, scripts_dir)

    try:
        from import_scunpacked import do_import, DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON
        if not os.path.exists(DEFAULT_SHIPS_JSON):
            flash(f"ships.json not found at: {DEFAULT_SHIPS_JSON}", "danger")
            return redirect(url_for("dashboard.index"))
        if not os.path.exists(DEFAULT_ITEMS_JSON):
            flash(f"ship-items.json not found at: {DEFAULT_ITEMS_JSON}", "danger")
            return redirect(url_for("dashboard.index"))

        summary = do_import(DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON, log=lambda x: None)
        flash(
            f"Game data updated: {summary['ships']} ships, "
            f"{summary['components']} components, {summary['weapons']} weapons.",
            "success",
        )
    except Exception as e:
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("dashboard.index"))
