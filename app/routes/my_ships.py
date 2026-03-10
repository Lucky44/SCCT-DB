from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from app import db
from app.models import Ship, MyShip, MyShipLoadout, ShipDefaultLoadout, ShipPowerAllocation, Component, Weapon


def get_power_stats(my_ship):
    """
    Calculate power generation and per-system pip draw for a ship.
    Uses ship-level Power.GenerationSegments and Power.UsedSegmentsGrouped from ships.json.
    """
    ship = my_ship.ship
    power_stats = {
        "total_generation": ship.power_generation_pips or 0,
        "systems": {},
        "coolers": []
    }

    # Collect equipped components by slot type (not component_type, which may differ)
    equipment_by_type = {
        "power_plant": [],
        "cooler": [],
        "shield_generator": [],
        "quantum_drive": [],
        "weapon": [],
    }
    has_power_plant_slot = False
    for slot in my_ship.loadout:
        if slot.slot_type == "power_plant":
            has_power_plant_slot = True
        if slot.component and slot.slot_type in equipment_by_type:
            equipment_by_type[slot.slot_type].append(slot.component)
        elif slot.weapon and slot.slot_type == "weapon":
            equipment_by_type["weapon"].append(slot.weapon)

    # Total power generation: sum equipped plants; if slots exist but all empty → 0
    equipped_plants = equipment_by_type["power_plant"]
    if has_power_plant_slot:
        power_stats["total_generation"] = float(sum(
            (p.stats or {}).get("power_generation") or 0 for p in equipped_plants
        ))

    segs = ship.power_segments or {}

    # Component-based systems: pip draw from actually equipped components/weapons
    power_stats["systems"]["shields"] = {
        "max_draw": float(sum((s.stats or {}).get("power_pips_max") or 0
                              for s in equipment_by_type["shield_generator"])),
        "equipment": equipment_by_type["shield_generator"],
    }
    power_stats["systems"]["quantum_drive"] = {
        "max_draw": float(sum((c.stats or {}).get("power_pips_max") or 0
                              for c in equipment_by_type["quantum_drive"])),
        "equipment": equipment_by_type["quantum_drive"],
    }
    power_stats["systems"]["weapons"] = {
        "max_draw": float(sum((w.stats or {}).get("power_pips_max") or 0
                              for w in equipment_by_type["weapon"])),
        "equipment": equipment_by_type["weapon"],
    }

    # Fixed systems: use ship-level segment data (no user-swappable component)
    power_stats["systems"]["thrust"] = {
        "max_draw": float(segs.get("FlightController") or 4), "equipment": []
    }
    power_stats["systems"]["radar"] = {
        "max_draw": float(segs.get("Radar") or 2), "equipment": []
    }
    power_stats["systems"]["life_support"] = {
        "max_draw": float(segs.get("LifeSupportGenerator") or 1), "equipment": []
    }

    # Coolers — each listed individually, pip draw from component stats
    for cooler in equipment_by_type["cooler"]:
        pip_max = (cooler.stats or {}).get("power_pips_max") or 3
        power_stats["coolers"].append({"name": cooler.name, "draw": pip_max})

    return power_stats


def calculate_default_allocation(power_stats):
    """
    Calculate default power allocation based on the rules:
    1. Allocate minimum to keep Radar, Life Support, and Coolers operational (1 pip each)
    2. Divide remainder equally to Shields, Weapons, Thrust, QD
    3. Extra pips go to Shields first, then Weapons, then QD, then Thrust
    
    Returns allocation dict with pip counts per system.
    """
    total_gen = power_stats["total_generation"]
    
    # Convert to pips (each pip = 1 power point, rounded)
    total_pips = int(total_gen)
    
    allocation = {}

    # Start by allocating minimum to fixed systems and coolers
    remaining_pips = total_pips
    
    # Radar and Life Support get 1 pip each (minimum to stay powered)
    allocation["radar"] = 1
    remaining_pips -= 1
    
    allocation["life_support"] = 1
    remaining_pips -= 1
    
    # Each cooler gets 1 pip minimum to stay operational
    for i, cooler in enumerate(power_stats["coolers"]):
        allocation[f"cooler_{i}"] = 1
        remaining_pips -= 1
    
    # Ensure we don't go negative if there are too many coolers
    if remaining_pips < 0:
        remaining_pips = 0
    
    # Allocate remaining to shields, weapons, thrust, quantum_drive equally
    # All 4 systems get equal share
    base_alloc = remaining_pips // 4
    remainder = remaining_pips % 4
    
    # Distribute remainder: Shields first, then Weapons, then QD, then Thrust
    allocation["shields"] = base_alloc + (1 if remainder >= 1 else 0)
    allocation["weapons"] = base_alloc + (1 if remainder >= 2 else 0)
    allocation["quantum_drive"] = base_alloc + (1 if remainder >= 3 else 0)
    allocation["thrust"] = base_alloc + (1 if remainder >= 4 else 0)
    
    return allocation


def get_or_create_power_allocation(my_ship):
    """Get the power allocation for a ship, or create default if it doesn't exist."""
    if my_ship.power_allocation:
        return my_ship.power_allocation.allocation_data
    
    # Create default allocation
    power_stats = get_power_stats(my_ship)
    allocation = calculate_default_allocation(power_stats)
    
    pa = ShipPowerAllocation(my_ship_id=my_ship.id, allocation_data=allocation)
    db.session.add(pa)
    db.session.commit()
    
    return allocation

my_ships_bp = Blueprint("my_ships", __name__, url_prefix="/my-hangar")


@my_ships_bp.route("/")
def index():
    ships = (
        db.session.query(MyShip)
        .join(Ship)
        .order_by(MyShip.display_order.nulls_last(), Ship.manufacturer, Ship.name)
        .all()
    )
    return render_template("my_hangar.html", ships=ships)


@my_ships_bp.route("/<int:my_ship_id>")
def detail(my_ship_id):
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    all_slots = (
        db.session.query(ShipDefaultLoadout)
        .filter_by(ship_id=my_ship.ship_id)
        .order_by(ShipDefaultLoadout.slot_type, ShipDefaultLoadout.mount_group, ShipDefaultLoadout.slot_number)
        .all()
    )
    my_slots = {(s.slot_type, s.slot_number): s for s in my_ship.loadout}

    default_slots = [s for s in all_slots if s.slot_type != "weapon"]
    weapon_groups_map = {}
    for slot in all_slots:
        if slot.slot_type != "weapon":
            continue
        key = (slot.mount_group or 0, slot.mount_type or "pilot", slot.mount_label or "")
        weapon_groups_map.setdefault(key, []).append(slot)
    weapon_groups = sorted(weapon_groups_map.items(), key=lambda x: x[0][0])

    # Calculate power stats and get allocation
    power_stats = get_power_stats(my_ship)
    current_allocation = get_or_create_power_allocation(my_ship)

    # Calculate used pips for display
    used_pips = sum(int(v) if isinstance(v, (int, float)) else 0 for v in current_allocation.values())

    # Build max_draw dict for template
    max_draw = {
        "weapons": power_stats["systems"]["weapons"]["max_draw"],
        "thrust": power_stats["systems"]["thrust"]["max_draw"],
        "shields": power_stats["systems"]["shields"]["max_draw"],
        "quantum_drive": power_stats["systems"]["quantum_drive"]["max_draw"],
        "radar": power_stats["systems"]["radar"]["max_draw"],
        "life_support": power_stats["systems"]["life_support"]["max_draw"],
    }
    for i, cooler in enumerate(power_stats["coolers"]):
        max_draw[f"cooler_{i}"] = cooler["draw"]

    # Build slot metadata map: (slot_type, slot_number) → ShipDefaultLoadout
    slot_meta = {(s.slot_type, s.slot_number): s for s in all_slots}

    # Compute live combat stats from equipped loadout
    equipped_shields = [s.component for s in my_ship.loadout if s.slot_type == "shield_generator" and s.component]

    pilot_burst = 0
    pilot_sustained = 0
    turret_burst = 0
    turret_sustained = 0

    for user_slot in my_ship.loadout:
        if user_slot.slot_type != "weapon" or not user_slot.weapon:
            continue
        meta = slot_meta.get((user_slot.slot_type, user_slot.slot_number))
        if not meta:
            continue
        # Skip PDC turrets
        if meta.mount_label == "PDC Turret":
            continue
        w_stats = user_slot.weapon.stats or {}
        burst = (w_stats.get("dps") or 0)
        sustained = (w_stats.get("dps_sustained") or 0)
        if meta.mount_type == "pilot":
            pilot_burst += burst
            pilot_sustained += sustained
        else:
            turret_burst += burst
            turret_sustained += sustained

    combat_stats = {
        "gun_dps": round(pilot_burst + turret_burst),
        "pilot_dps_burst": round(pilot_burst),
        "pilot_dps_sustained": round(pilot_sustained),
        "turret_dps_burst": round(turret_burst),
        "turret_dps_sustained": round(turret_sustained),
        "shield_hp": round(sum((s.stats or {}).get("shield_hp") or 0 for s in equipped_shields)),
        "shield_regen": round(sum((s.stats or {}).get("shield_regen") or 0 for s in equipped_shields)),
    }

    return render_template(
        "ship_detail.html",
        my_ship=my_ship,
        default_slots=default_slots,
        weapon_groups=weapon_groups,
        my_slots=my_slots,
        power_stats=power_stats,
        current_allocation=current_allocation,
        used_pips=used_pips,
        max_draw=max_draw,
        combat_stats=combat_stats,
    )


@my_ships_bp.route("/<int:my_ship_id>/details")
def ship_details(my_ship_id):
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    return render_template("ship_details.html", my_ship=my_ship)


@my_ships_bp.route("/add/<int:ship_id>", methods=["POST"])
def add(ship_id):
    ship = db.session.get(Ship, ship_id) or abort(404)
    nickname = request.form.get("nickname", "").strip() or None
    notes = request.form.get("notes", "").strip() or None
    my_ship = MyShip(ship_id=ship.id, nickname=nickname, notes=notes)
    db.session.add(my_ship)
    db.session.flush()

    # Pre-populate loadout slots from the ship's default loadout
    for slot in ship.default_loadout:
        entry = MyShipLoadout(
            my_ship_id=my_ship.id,
            slot_type=slot.slot_type,
            slot_number=slot.slot_number,
            component_id=slot.default_component_id,
            weapon_id=slot.default_weapon_id,
        )
        db.session.add(entry)

    db.session.commit()
    flash(f'"{ship.name}" added to your fleet.', "success")
    return redirect(url_for("my_ships.detail", my_ship_id=my_ship.id))


@my_ships_bp.route("/<int:my_ship_id>/edit", methods=["POST"])
def edit(my_ship_id):
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    my_ship.nickname = request.form.get("nickname", "").strip() or None
    my_ship.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    flash("Ship updated.", "success")
    return redirect(url_for("my_ships.detail", my_ship_id=my_ship.id))


@my_ships_bp.route("/<int:my_ship_id>/delete", methods=["POST"])
def delete(my_ship_id):
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    db.session.delete(my_ship)
    db.session.commit()
    flash("Ship removed from your fleet.", "info")
    return redirect(url_for("my_ships.index"))


@my_ships_bp.route("/<int:my_ship_id>/power/save", methods=["POST"])
def save_power_allocation(my_ship_id):
    """Save the user's power allocation for a ship."""
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    data = request.get_json()
    allocation = data.get("allocation", {})
    
    if not my_ship.power_allocation:
        pa = ShipPowerAllocation(my_ship_id=my_ship.id, allocation_data=allocation)
        db.session.add(pa)
    else:
        my_ship.power_allocation.allocation_data = allocation
    
    db.session.commit()
    return jsonify({"success": True})


@my_ships_bp.route("/<int:my_ship_id>/power/reset", methods=["POST"])
def reset_power_allocation(my_ship_id):
    """Reset power allocation to default."""
    my_ship = db.session.get(MyShip, my_ship_id) or abort(404)
    power_stats = get_power_stats(my_ship)
    allocation = calculate_default_allocation(power_stats)
    
    if not my_ship.power_allocation:
        pa = ShipPowerAllocation(my_ship_id=my_ship.id, allocation_data=allocation)
        db.session.add(pa)
    else:
        my_ship.power_allocation.allocation_data = allocation
    
    db.session.commit()
    return jsonify({"success": True, "allocation": allocation})
