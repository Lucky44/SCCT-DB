import os
import sys
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from app import db
from app.models import Ship, Component, Weapon, MyShip, MyInventory

dashboard_bp = Blueprint("dashboard", __name__)

STATE_FILE = "import_state.json"


def _state_path():
    return os.path.join(current_app.instance_path, STATE_FILE)


def _read_state():
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_state(ships_path, items_path):
    state = {
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "ships_mtime": os.path.getmtime(ships_path),
        "items_mtime": os.path.getmtime(items_path),
    }
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f)
    return state


def _time_ago(dt):
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = seconds // 86400
    return f"{d} day{'s' if d != 1 else ''} ago"


def _get_data_status(ships_path, items_path):
    state = _read_state()
    if state is None:
        return {"known": False}
    try:
        ships_mtime = os.path.getmtime(ships_path)
        items_mtime = os.path.getmtime(items_path)
    except OSError:
        return {"known": False}
    update_available = (
        ships_mtime > state["ships_mtime"] or
        items_mtime > state["items_mtime"]
    )
    imported_at = datetime.fromisoformat(state["imported_at"])
    return {
        "known": True,
        "update_available": update_available,
        "imported_at_ago": _time_ago(imported_at),
    }


@dashboard_bp.route("/")
def index():
    stats = {
        "total_ships_ref": db.session.query(Ship).count(),
        "total_components_ref": db.session.query(Component).count(),
        "total_weapons_ref": db.session.query(Weapon).count(),
        "my_ship_count": db.session.query(MyShip).count(),
        "my_inventory_count": db.session.query(MyInventory).count(),
    }

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    scripts_dir = os.path.join(project_root, "scripts")
    sys.path.insert(0, scripts_dir)
    try:
        from import_scunpacked import DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON
        # Bootstrap state file on first load if data exists but state is missing
        if _read_state() is None and db.session.query(Ship).count() > 0:
            try:
                _write_state(DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON)
            except Exception:
                pass
        data_status = _get_data_status(DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON)
    except Exception:
        data_status = {"known": False}

    return render_template("dashboard.html", stats=stats, data_status=data_status)


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
        _write_state(DEFAULT_SHIPS_JSON, DEFAULT_ITEMS_JSON)
        flash(
            f"Game data updated: {summary['ships']} ships, "
            f"{summary['components']} components, {summary['weapons']} weapons.",
            "success",
        )
    except Exception as e:
        flash(f"Import failed: {e}", "danger")

    return redirect(url_for("dashboard.index"))
