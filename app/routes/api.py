from datetime import datetime
import json

from flask import Blueprint, jsonify, request, abort, Response
from app import db
from app.models import Component, Weapon, Ship, MyShip, MyShipLoadout, MyInventory, ShipDefaultLoadout, ShipPowerAllocation

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
    if size is not None and size > 0:
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


@api_bp.route("/check-update")
def check_update():
    """Check GitHub for a newer release. Cached 1 hr."""
    from app.updater import check_for_update
    return jsonify(check_for_update())


@api_bp.route("/update/download", methods=["POST"])
def update_download():
    """Download the new exe to disk. Blocks until complete."""
    from app.updater import download_update
    data = request.get_json(force=True)
    url  = data.get("download_url")
    if not url:
        return jsonify({"ok": False, "error": "No download_url provided"}), 400
    return jsonify(download_update(url))


@api_bp.route("/update/restart", methods=["POST"])
def update_restart():
    """Launch the swap batch script and exit. App will restart as new version."""
    from app.updater import launch_update_and_exit
    launch_update_and_exit()
    return jsonify({"ok": True})   # only reached in dev mode


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


@api_bp.route("/export")
def export_data():
    """Export all user data (hangar, loadouts, inventory) as a JSON backup file."""
    hangar = []
    for ms in db.session.query(MyShip).order_by(MyShip.display_order).all():
        loadout = []
        for slot in ms.loadout:
            entry = {"slot_type": slot.slot_type, "slot_number": slot.slot_number}
            if slot.component_id and slot.component:
                entry.update({
                    "component_name": slot.component.name,
                    "component_type": slot.component.component_type,
                    "component_size": slot.component.size,
                    "component_grade": slot.component.grade,
                })
            elif slot.weapon_id and slot.weapon:
                entry.update({
                    "weapon_name": slot.weapon.name,
                    "weapon_size": slot.weapon.size,
                })
            loadout.append(entry)

        hangar.append({
            "ship_name": ms.ship.name if ms.ship else None,
            "nickname": ms.nickname,
            "notes": ms.notes,
            "display_order": ms.display_order,
            "loadout": loadout,
            "power_allocation": ms.power_allocation.allocation_data if ms.power_allocation else None,
        })

    inventory = []
    for inv in db.session.query(MyInventory).all():
        entry = {"quantity": inv.quantity, "location": inv.location, "notes": inv.notes}
        if inv.component_id and inv.component:
            entry.update({
                "component_name": inv.component.name,
                "component_type": inv.component.component_type,
                "component_size": inv.component.size,
                "component_grade": inv.component.grade,
            })
        elif inv.weapon_id and inv.weapon:
            entry.update({
                "weapon_name": inv.weapon.name,
                "weapon_size": inv.weapon.size,
            })
        inventory.append(entry)

    payload = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "hangar": hangar,
        "inventory": inventory,
    }
    filename = f"scct-backup-{datetime.utcnow().strftime('%Y%m%d')}.json"
    return Response(
        json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@api_bp.route("/import", methods=["POST"])
def import_data():
    """Replace all user data from a JSON backup file."""
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "No file provided"}), 400

    try:
        data = json.loads(file.read())
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON file"}), 400

    if "hangar" not in data or "inventory" not in data:
        return jsonify({"ok": False, "error": "Invalid backup format — missing hangar or inventory keys"}), 400

    # Wipe existing user data
    db.session.query(ShipPowerAllocation).delete()
    db.session.query(MyShipLoadout).delete()
    db.session.query(MyShip).delete()
    db.session.query(MyInventory).delete()

    stats = {"ships_imported": 0, "ships_skipped": 0, "inventory_imported": 0, "inventory_skipped": 0}

    for entry in data.get("hangar", []):
        ship = db.session.query(Ship).filter_by(name=entry.get("ship_name")).first()
        if not ship:
            stats["ships_skipped"] += 1
            continue

        ms = MyShip(
            ship_id=ship.id,
            nickname=entry.get("nickname"),
            notes=entry.get("notes"),
            display_order=entry.get("display_order"),
        )
        db.session.add(ms)
        db.session.flush()

        for slot in entry.get("loadout", []):
            msl = MyShipLoadout(
                my_ship_id=ms.id,
                slot_type=slot["slot_type"],
                slot_number=slot["slot_number"],
            )
            if "component_name" in slot:
                comp = db.session.query(Component).filter_by(
                    name=slot["component_name"],
                    component_type=slot.get("component_type"),
                    size=slot.get("component_size"),
                ).first()
                if comp:
                    msl.component_id = comp.id
            elif "weapon_name" in slot:
                weap = db.session.query(Weapon).filter_by(
                    name=slot["weapon_name"],
                    size=slot.get("weapon_size"),
                ).first()
                if weap:
                    msl.weapon_id = weap.id
            db.session.add(msl)

        if entry.get("power_allocation"):
            db.session.add(ShipPowerAllocation(
                my_ship_id=ms.id,
                allocation_data=entry["power_allocation"],
            ))

        stats["ships_imported"] += 1

    for entry in data.get("inventory", []):
        inv = MyInventory(
            quantity=entry.get("quantity", 1),
            location=entry.get("location", "storage"),
            notes=entry.get("notes"),
        )
        if "component_name" in entry:
            comp = db.session.query(Component).filter_by(
                name=entry["component_name"],
                component_type=entry.get("component_type"),
                size=entry.get("component_size"),
            ).first()
            if comp:
                inv.component_id = comp.id
                db.session.add(inv)
                stats["inventory_imported"] += 1
            else:
                stats["inventory_skipped"] += 1
        elif "weapon_name" in entry:
            weap = db.session.query(Weapon).filter_by(
                name=entry["weapon_name"],
                size=entry.get("weapon_size"),
            ).first()
            if weap:
                inv.weapon_id = weap.id
                db.session.add(inv)
                stats["inventory_imported"] += 1
            else:
                stats["inventory_skipped"] += 1

    db.session.commit()
    return jsonify({"ok": True, **stats})
