from flask import Blueprint, jsonify, request, abort
from app import db
from app.models import Component, Weapon, MyShip, MyShipLoadout, MyInventory, ShipDefaultLoadout

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _power_pips(comp):
    """Return (pips_min, pips_max) from ResourceNetwork.Usage.Power stored in stats."""
    stats = comp.stats or {}
    pmin = stats.get("power_pips_min")
    pmax = stats.get("power_pips_max")
    if pmin is None and pmax is None:
        return None
    return {"min": pmin, "max": pmax}


@api_bp.route("/components")
def components():
    """Return components filtered by type and size — used by the slot picker."""
    comp_type = request.args.get("type", "")
    size = request.args.get("size", type=int)

    q = db.session.query(Component)
    if comp_type:
        q = q.filter(Component.component_type == comp_type)
    if size:
        q = q.filter(Component.size == size)

    results = [
        {
            "id": c.id,
            "name": c.name,
            "type": c.component_type,
            "size": c.size,
            "grade": c.grade,
            "class": c.class_,
            "manufacturer": c.manufacturer,
            "stats": c.stats or {},
            "power_pips": _power_pips(c),
        }
        for c in q.order_by(Component.grade, Component.name).all()
    ]
    return jsonify(results)


@api_bp.route("/weapons")
def weapons():
    """Return weapons filtered by size — used by the slot picker."""
    size = request.args.get("size", type=int)

    q = db.session.query(Weapon)
    if size:
        q = q.filter(Weapon.size == size)

    seen = set()
    results = []
    for w in q.order_by(Weapon.weapon_type, Weapon.name).all():
        key = (w.name, w.size)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "id": w.id,
            "name": w.name,
            "type": w.weapon_type,
            "size": w.size,
            "mount_type": w.mount_type,
            "damage_type": w.damage_type,
            "manufacturer": w.manufacturer,
            "dps": (w.stats or {}).get("dps"),
            "speed": (w.stats or {}).get("speed"),
        })
    return jsonify(results)


@api_bp.route("/component/<int:component_id>")
def component_detail(component_id):
    """Return full component data including type-specific stats."""
    comp = db.session.get(Component, component_id) or abort(404)
    return jsonify({
        "id": comp.id,
        "name": comp.name,
        "type": comp.component_type,
        "size": comp.size,
        "grade": comp.grade,
        "class": comp.class_,
        "manufacturer": comp.manufacturer,
        "stats": comp.stats or {},
    })


@api_bp.route("/weapon/<int:weapon_id>")
def weapon_detail(weapon_id):
    """Return full weapon data including stats."""
    w = db.session.get(Weapon, weapon_id) or abort(404)
    return jsonify({
        "id": w.id,
        "name": w.name,
        "type": w.weapon_type,
        "size": w.size,
        "mount_type": w.mount_type,
        "manufacturer": w.manufacturer,
        "stats": w.stats or {},
    })


@api_bp.route("/hangar/reorder", methods=["POST"])
def hangar_reorder():
    """Save the user's custom hangar card order."""
    ids = request.get_json(force=True).get("order", [])
    for position, ship_id in enumerate(ids):
        ship = db.session.get(MyShip, ship_id)
        if ship:
            ship.display_order = position
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/loadout/<int:slot_id>/equip", methods=["POST"])
def equip(slot_id):
    """Equip a component or weapon in a loadout slot."""
    slot = db.session.get(MyShipLoadout, slot_id) or abort(404)
    data = request.get_json(force=True)

    new_component_id = data.get("component_id")
    new_weapon_id    = data.get("weapon_id")

    # Inventory check — only when equipping something new (not clearing, not same item)
    if new_component_id and new_component_id != slot.component_id:
        count_on_ships = db.session.query(MyShipLoadout).filter_by(component_id=new_component_id).count()
        inv = db.session.query(MyInventory).filter_by(component_id=new_component_id, weapon_id=None).first()
        total_owned = inv.quantity if inv else 0
        if total_owned <= count_on_ships:
            comp = db.session.get(Component, new_component_id)
            return jsonify({
                "status": "no_inventory",
                "item_type": "component",
                "item_id": new_component_id,
                "name": comp.name if comp else "Unknown",
            })

    elif new_weapon_id and new_weapon_id != slot.weapon_id:
        count_on_ships = db.session.query(MyShipLoadout).filter_by(weapon_id=new_weapon_id).count()
        inv = db.session.query(MyInventory).filter_by(weapon_id=new_weapon_id, component_id=None).first()
        total_owned = inv.quantity if inv else 0
        if total_owned <= count_on_ships:
            weap = db.session.get(Weapon, new_weapon_id)
            return jsonify({
                "status": "no_inventory",
                "item_type": "weapon",
                "item_id": new_weapon_id,
                "name": weap.name if weap else "Unknown",
            })

    slot.component_id = new_component_id
    slot.weapon_id    = new_weapon_id
    db.session.commit()

    return jsonify({"ok": True, "slot_id": slot.id})


@api_bp.route("/inventory/increment", methods=["POST"])
def inventory_increment():
    """Increment (or create) a MyInventory record by 1, then proceed with equip."""
    data = request.get_json(force=True)
    component_id = data.get("component_id")
    weapon_id    = data.get("weapon_id")

    if component_id:
        inv = db.session.query(MyInventory).filter_by(component_id=component_id, weapon_id=None).first()
        if inv:
            inv.quantity += 1
        else:
            inv = MyInventory(component_id=component_id, quantity=1)
            db.session.add(inv)
    elif weapon_id:
        inv = db.session.query(MyInventory).filter_by(weapon_id=weapon_id, component_id=None).first()
        if inv:
            inv.quantity += 1
        else:
            inv = MyInventory(weapon_id=weapon_id, quantity=1)
            db.session.add(inv)
    else:
        return jsonify({"ok": False, "error": "No item specified"}), 400

    db.session.commit()
    return jsonify({"ok": True, "quantity": inv.quantity})
