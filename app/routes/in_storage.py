from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from app import db
from app.models import Component, Weapon, MyInventory, MyShipLoadout, MyShip

in_storage_bp = Blueprint("in_storage", __name__, url_prefix="/in-storage")


def _on_ship_maps():
    """Return dicts mapping component_id/weapon_id → list of ship display names."""
    comp_map = defaultdict(list)
    weap_map = defaultdict(list)
    rows = (
        db.session.query(MyShipLoadout, MyShip)
        .join(MyShip, MyShipLoadout.my_ship_id == MyShip.id)
        .filter(
            (MyShipLoadout.component_id.isnot(None)) |
            (MyShipLoadout.weapon_id.isnot(None))
        )
        .all()
    )
    for slot, my_ship in rows:
        full_name = my_ship.ship.name
        model_name = ' '.join(full_name.split()[1:]) if ' ' in full_name else full_name
        label = my_ship.nickname or model_name
        if slot.component_id:
            comp_map[slot.component_id].append(label)
        if slot.weapon_id:
            weap_map[slot.weapon_id].append(label)
    return comp_map, weap_map


@in_storage_bp.route("/")
def index():
    # Get user's inventory components, grouped by type
    all_user_components = (
        db.session.query(MyInventory)
        .filter(MyInventory.component_id.isnot(None))
        .join(Component, MyInventory.component_id == Component.id)
        .order_by(Component.name)
        .all()
    )

    components_by_type = {
        "power_plant": [],
        "cooler": [],
        "shield_generator": [],
        "quantum_drive": [],
    }
    for comp in all_user_components:
        comp_type = comp.component.component_type
        if comp_type in components_by_type:
            components_by_type[comp_type].append(comp)
    
    weapons = (
        db.session.query(MyInventory)
        .filter(MyInventory.weapon_id.isnot(None))
        .join(Weapon, MyInventory.weapon_id == Weapon.id)
        .order_by(Weapon.weapon_type, Weapon.size)
        .all()
    )

    comp_on_ship, weap_on_ship = _on_ship_maps()

    # Auto-correct any Total Owned values that are below the on-ships count
    needs_commit = False
    for item in all_user_components:
        on_ships = len(comp_on_ship.get(item.component_id, []))
        if item.quantity < on_ships:
            item.quantity = on_ships
            needs_commit = True
    for item in weapons:
        on_ships = len(weap_on_ship.get(item.weapon_id, []))
        if item.quantity < on_ships:
            item.quantity = on_ships
            needs_commit = True
    if needs_commit:
        db.session.commit()

    # All reference components/weapons for the add-item dropdowns, grouped by type
    all_components = (
        db.session.query(Component)
        .order_by(Component.component_type, Component.size, Component.grade, Component.name)
        .all()
    )
    all_weapons = (
        db.session.query(Weapon)
        .order_by(Weapon.weapon_type, Weapon.size, Weapon.name)
        .all()
    )

    # prepare lists for filter dropdowns (unique and sorted)
    comp_types = sorted({c.component_type for c in all_components if c.component_type})
    comp_sizes = sorted({c.size for c in all_components if c.size is not None})
    comp_grades = sorted({c.grade for c in all_components if c.grade})
    comp_classes = sorted({c.class_ for c in all_components if c.class_})

    return render_template(
        "in_storage.html",
        components_by_type=components_by_type,
        weapons=weapons,
        comp_on_ship=comp_on_ship,
        weap_on_ship=weap_on_ship,
        all_components=all_components,
        all_weapons=all_weapons,
        comp_types=comp_types,
        comp_sizes=comp_sizes,
        comp_grades=comp_grades,
        comp_classes=comp_classes,
    )


@in_storage_bp.route("/add", methods=["POST"])
def add():
    component_id = request.form.get("component_id") or None
    weapon_id = request.form.get("weapon_id") or None
    quantity = int(request.form.get("quantity", 1))
    location = request.form.get("location", "storage").strip()
    notes = request.form.get("notes", "").strip() or None

    if not component_id and not weapon_id:
        flash("Select a component or weapon to add.", "warning")
        return redirect(url_for("in_storage.index"))

    cid = int(component_id) if component_id else None
    wid = int(weapon_id) if weapon_id else None

    # Upsert: increment existing record rather than creating a duplicate
    existing = None
    if cid:
        existing = MyInventory.query.filter_by(component_id=cid).first()
    elif wid:
        existing = MyInventory.query.filter_by(weapon_id=wid).first()

    if existing:
        existing.quantity += quantity
        if notes:
            existing.notes = notes
    else:
        entry = MyInventory(
            component_id=cid,
            weapon_id=wid,
            quantity=quantity,
            location=location,
            notes=notes,
        )
        db.session.add(entry)

    db.session.commit()
    flash("Item added to inventory.", "success")
    return redirect(url_for("in_storage.index"))


@in_storage_bp.route("/<int:item_id>/update", methods=["POST"])
def update(item_id):
    item = db.session.get(MyInventory, item_id) or abort(404)
    qty = request.form.get("quantity", "0")
    item.quantity = max(0, int(qty)) if qty.isdigit() else 0
    item.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    flash("Inventory updated.", "success")
    return redirect(url_for("in_storage.index"))


@in_storage_bp.route("/<int:item_id>/delete", methods=["POST"])
def delete(item_id):
    item = db.session.get(MyInventory, item_id) or abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from inventory.", "info")
    return redirect(url_for("in_storage.index"))
