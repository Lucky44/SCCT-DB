"""
Import ships, components, and weapons from scunpacked-data JSON files into the SCCT database.

Usage:
    python scripts/import_scunpacked.py [--ships PATH] [--items PATH]

Defaults to the sibling SC-Component-Tracker project's copies of ships.json and
ship-items.json, but any paths can be supplied.

This script is safe to re-run: it wipes and repopulates all reference tables
(ships, components, weapons, ship_default_loadout) while leaving user tables
(my_ships, my_ship_loadout, my_inventory) untouched.
"""

import sys
import os
import argparse
import json

# ---------------------------------------------------------------------------
# Make sure we can import the Flask app from the project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db
from app.models import Ship, Component, Weapon, ShipDefaultLoadout, MyShip, MyShipLoadout

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# When running as a PyInstaller bundle, data files are in sys._MEIPASS/data/
# When running from source, fall back to the sibling SC-Component-Tracker dir
if getattr(sys, "frozen", False):
    _DATA_DIR = os.path.join(sys._MEIPASS, "data")
else:
    _DATA_DIR = os.path.join(PROJECT_ROOT, "data")

_LEGACY_DIR = os.path.join(PROJECT_ROOT, "..", "SC-Component-Tracker")

def _find_json(filename):
    bundled = os.path.join(_DATA_DIR, filename)
    if os.path.exists(bundled):
        return bundled
    return os.path.join(_LEGACY_DIR, filename)

DEFAULT_SHIPS_JSON = _find_json("ships.json")
DEFAULT_ITEMS_JSON = _find_json("ship-items.json")
DEFAULT_OVERRIDES_JSON = _find_json("ship_slot_overrides.json")
DEFAULT_DATA_OVERRIDES_JSON = _find_json("ship_data_overrides.json")

# Types we care about as components (non-weapon ship equipment)
COMPONENT_TYPES = {"PowerPlant", "Cooler", "Shield", "QuantumDrive", "Radar"}

# Types we care about as weapons
WEAPON_TYPES = {"WeaponGun"}

# Map raw item type → our DB component_type string
COMPONENT_TYPE_MAP = {
    "PowerPlant": "power_plant",
    "Cooler": "cooler",
    "Shield": "shield_generator",
    "QuantumDrive": "quantum_drive",
    "Radar": "radar",
}

# Map raw item type → our DB weapon_type string
WEAPON_SUBTYPE_MAP = {
    "WeaponGun": None,     # use subType from data
}

# Slot types in ship loadouts we want to record
SLOT_TYPE_MAP = {
    "Cooler": "cooler",
    "PowerPlant": "power_plant",
    "Shield": "shield_generator",
    "QuantumDrive": "quantum_drive",
    "Radar": "radar",
    "WeaponGun": "weapon",
}

# Ship size integer → size_category string
def map_size_category(size_int):
    if size_int is None:
        return None
    if size_int <= 2:
        return "small"
    if size_int == 3:
        return "medium"
    if size_int <= 5:
        return "large"
    return "capital"

# Numeric grade → letter grade (1=A best, 4=D cheapest)
GRADE_MAP = {1: "A", 2: "B", 3: "C", 4: "D"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_name(name):
    """Return None for placeholder names, else the name as-is."""
    if not name or name.strip() in ("<= PLACEHOLDER =>", ""):
        return None
    return name.strip()


def get_desc_data(item):
    """Pull Grade and Class from stdItem.DescriptionData if present."""
    std = item.get("stdItem") or {}
    return std.get("DescriptionData") or {}


def extract_stats(item, itype):
    """Extract type-specific stats from a raw item's stdItem block."""
    std = item.get("stdItem") or {}
    rn_usage_power = (std.get("ResourceNetwork", {}).get("Usage", {}).get("Power", {}))

    if itype == "Cooler":
        emission = std.get("Emission", {})
        durability = std.get("Durability", {})
        distortion = std.get("Distortion", {})
        rn = std.get("ResourceNetwork", {})
        return {
            "cooling_generation": rn.get("Generation", {}).get("Coolant"),
            "power_pips_min": rn_usage_power.get("Minimum"),
            "power_pips_max": rn_usage_power.get("Maximum"),
            "em_signature": emission.get("Em", {}).get("Maximum"),
            "ir_signature": emission.get("Ir"),
            "health": durability.get("Health"),
            "distortion_shutdown_damage": distortion.get("Maximum"),
            "distortion_decay_delay": distortion.get("DecayDelay"),
            "distortion_decay_rate": distortion.get("DecayRate"),
            "distortion_recovery_ratio": distortion.get("RecoveryRatio"),
            "distortion_warning_ratio": distortion.get("WarningRatio"),
        }
    if itype == "PowerPlant":
        emission = std.get("Emission", {})
        durability = std.get("Durability", {})
        distortion = std.get("Distortion", {})
        rn = std.get("ResourceNetwork", {})
        return {
            "power_generation": rn.get("Generation", {}).get("Power"),
            "em_max": emission.get("Em", {}).get("Maximum"),
            "health": durability.get("Health"),
            "distortion_shutdown_damage": distortion.get("Maximum"),
            "distortion_decay_delay": distortion.get("DecayDelay"),
            "distortion_decay_rate": distortion.get("DecayRate"),
            "distortion_recovery_ratio": distortion.get("RecoveryRatio"),
            "distortion_warning_ratio": distortion.get("WarningRatio"),
        }
    if itype == "Shield":
        shield = std.get("Shield", {})
        emission = std.get("Emission", {})
        durability = std.get("Durability", {})
        distortion = std.get("Distortion", {})
        return {
            "shield_hp": shield.get("MaxShieldHealth"),
            "shield_regen": shield.get("MaxShieldRegen"),
            "regen_delay_damaged": shield.get("DamagedDelay"),
            "regen_delay_downed": shield.get("DownedDelay"),
            "power_pips_min": rn_usage_power.get("Minimum"),
            "power_pips_max": rn_usage_power.get("Maximum"),
            "em_signature": emission.get("Em", {}).get("Maximum"),
            "ir_signature": emission.get("Ir"),
            "health": durability.get("Health"),
            "distortion_shutdown_damage": distortion.get("Maximum"),
            "distortion_decay_delay": distortion.get("DecayDelay"),
            "distortion_decay_rate": distortion.get("DecayRate"),
            "distortion_recovery_ratio": distortion.get("RecoveryRatio"),
            "distortion_warning_ratio": distortion.get("WarningRatio"),
        }
    if itype == "QuantumDrive":
        qd = std.get("QuantumDrive", {})
        jump = qd.get("StandardJump", {})
        durability = std.get("Durability", {})
        return {
            "spool_time": jump.get("SpoolUpTime"),
            "cooldown": jump.get("CooldownTime"),
            "drive_speed": jump.get("DriveSpeed"),
            "fuel_requirement": qd.get("QuantumFuelRequirement"),
            "power_pips_min": rn_usage_power.get("Minimum"),
            "power_pips_max": rn_usage_power.get("Maximum"),
            "health": durability.get("Health"),
        }
    if itype == "Radar":
        radar = std.get("Radar", {})
        sensitivity = radar.get("Sensitivity", {})
        durability = std.get("Durability", {})
        return {
            "sensitivity_ir": sensitivity.get("IR"),
            "sensitivity_em": sensitivity.get("EM"),
            "sensitivity_cs": sensitivity.get("CS"),
            "sensitivity_rs": sensitivity.get("RS"),
            "cooldown": radar.get("Cooldown"),
            "health": durability.get("Health"),
        }
    if itype == "WeaponGun":
        weapon = std.get("Weapon", {})
        damage = weapon.get("Damage", {})
        durability = std.get("Durability", {})
        ammo = std.get("Ammunition", {})
        return {
            "dps": damage.get("DpsTotal"),
            "dps_sustained": damage.get("Sustained60s"),
            "damage_per_shot": damage.get("AlphaTotal"),
            "fire_rate": weapon.get("RateOfFire"),
            "ammo_count": weapon.get("Capacity"),
            "range": weapon.get("EffectiveRange"),
            "speed": ammo.get("Speed"),
            "power_pips_max": rn_usage_power.get("Maximum"),
            "health": durability.get("Health"),
        }
    return None


def get_manufacturer(item):
    std = item.get("stdItem") or {}
    mfr = std.get("Manufacturer") or {}
    name = mfr.get("Name", "")
    return name if name and name != "Unknown Manufacturer" else None


def slot_types_from_entry(entry):
    """Return the list of type strings from a loadout entry's ItemTypes."""
    return [it.get("Type", "") for it in entry.get("ItemTypes", [])]


POSITION_WORDS = {
    "Top", "Bottom", "Rear", "Front", "Main", "Upper", "Lower",
    "Left", "Right", "Side", "Back", "Bubble", "Wing", "Ball",
    "Chin", "Belly", "Bay", "Nose", "Tail", "Center", "Mid",
}
CAMEL_POSITIONS = {
    "RearTop": "Rear Top", "RearBottom": "Rear Bottom",
    "FrontTop": "Front Top", "FrontBottom": "Front Bottom",
}


def classify_turret(class_name):
    """Return (mount_type, mount_label) for a named turret entry."""
    cn = class_name or ""
    if "PDC" in cn:
        return ("remote_turret", "PDC Turret")
    is_manned = "Manned" in cn
    parts = cn.split("_")
    positions = []
    for part in parts:
        if part in POSITION_WORDS:
            positions.append(part)
        elif part in CAMEL_POSITIONS:
            positions.append(CAMEL_POSITIONS[part])
    pos = " ".join(positions)
    if is_manned:
        return ("manned_turret", f"{pos} Manned Turret".strip())
    return ("remote_turret", f"{pos} Remote Turret".strip())


def iter_gun_slots(entry):
    """
    Yield (slot_size, class_name) for each WeaponGun inside a mount entry.
    Handles several levels:
      - turret → direct gun  (WeaponGun type, no Gimbal in name)
      - turret → gimbal sub-mount (WeaponGun+Turret) → gun inside
      - turret → gimbal sub-mount (Turret only, e.g. Mount_Gimbal_S8_Perseus) → gun inside
    """
    for sub in entry.get("Loadout", []):
        sub_types = slot_types_from_entry(sub)
        sub_cn = sub.get("ClassName") or ""

        if "WeaponGun" in sub_types:
            if "Gimbal" in sub_cn:
                # Gimbal mount with WeaponGun+Turret → look one level deeper for actual gun
                inner_gun = None
                for inner in sub.get("Loadout", []):
                    inner_types = slot_types_from_entry(inner)
                    if "WeaponGun" in inner_types and "Gimbal" not in (inner.get("ClassName") or ""):
                        inner_gun = inner.get("ClassName")
                        break
                yield sub.get("MaxSize"), inner_gun
            else:
                # Direct WeaponGun (fixed mount)
                yield sub.get("MaxSize"), sub_cn
        elif any("Turret" in t for t in sub_types) and "Gimbal" in sub_cn:
            # Gimbal mount with only Turret type (no WeaponGun at this level,
            # e.g. Mount_Gimbal_S8_Perseus) — look inside for the gun
            inner_gun = None
            for inner in sub.get("Loadout", []):
                inner_types = slot_types_from_entry(inner)
                if "WeaponGun" in inner_types:
                    inner_gun = inner.get("ClassName")
                    break
            yield sub.get("MaxSize"), inner_gun


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def do_import(ships_path, items_path, log=print):
    """
    Core import logic. Must be called within an active Flask app context.
    `log` is a callable used for progress output (default: print).
    Returns a summary dict.
    """
    # ----------------------------------------------------------------
    # 1. Load JSON files
    # ----------------------------------------------------------------
    log(f"Loading ships from:  {ships_path}")
    with open(ships_path, encoding="utf-8") as f:
        raw_ships = json.load(f)

    log(f"Loading items from:  {items_path}")
    with open(items_path, encoding="utf-8") as f:
        raw_items = json.load(f)

    overrides_path = DEFAULT_OVERRIDES_JSON
    if os.path.exists(overrides_path):
        log(f"Loading overrides from: {overrides_path}")
        with open(overrides_path, encoding="utf-8") as f:
            raw_overrides = json.load(f)
        # Strip the readme key
        ship_slot_overrides = {k: v for k, v in raw_overrides.items() if not k.startswith("_")}
    else:
        ship_slot_overrides = {}

    # ----------------------------------------------------------------
    # 2. Wipe reference tables (preserves user data)
    # ----------------------------------------------------------------
    log("Clearing reference tables …")
    db.session.query(ShipDefaultLoadout).delete()
    db.session.query(Ship).delete()
    db.session.query(Component).delete()
    db.session.query(Weapon).delete()
    db.session.commit()

    # ----------------------------------------------------------------
    # 3a. Build missile damage lookup (className → DamageTotal)
    # ----------------------------------------------------------------
    missile_damage_by_class = {}
    for item in raw_items:
        if item.get("type") == "Missile":
            dmg = (item.get("stdItem") or {}).get("Missile", {}).get("DamageTotal")
            if dmg is not None:
                missile_damage_by_class[item["className"]] = dmg

    # ----------------------------------------------------------------
    # 3. Import components from SCUnpacked
    # ----------------------------------------------------------------
    log("Importing components …")
    component_by_class = {}   # className → Component (DB object)
    component_seen = {}       # (name, type, size, grade) → Component (deduplicate)

    for item in raw_items:
        itype = item.get("type", "")
        if itype not in COMPONENT_TYPES:
            continue

        name = clean_name(item.get("name"))
        if not name:
            continue

        desc = get_desc_data(item)
        grade_letter = desc.get("Grade") or GRADE_MAP.get(item.get("grade"))
        class_str = (desc.get("Class") or "").lower() or None
        mfr = get_manufacturer(item) or (desc.get("Manufacturer") or None)
        size = item.get("size")
        comp_type = COMPONENT_TYPE_MAP[itype]

        dedup_key = (name, comp_type, size, grade_letter)

        if dedup_key in component_seen:
            component_by_class[item["className"]] = component_seen[dedup_key]
            continue

        comp = Component(
            name=name,
            component_type=comp_type,
            size=size,
            grade=grade_letter,
            class_=class_str,
            manufacturer=mfr,
            stats=extract_stats(item, itype),
        )
        db.session.add(comp)
        db.session.flush()

        component_by_class[item["className"]] = comp
        component_seen[dedup_key] = comp

    db.session.commit()
    log(f"  → {db.session.query(Component).count()} components")

    # ----------------------------------------------------------------
    # 4. Import weapons
    # ----------------------------------------------------------------
    log("Importing weapons …")
    weapon_by_class = {}   # className → Weapon (DB object)
    weapon_seen = {}       # (name, size) → Weapon (deduplicate display names)

    for item in raw_items:
        itype = item.get("type", "")
        if itype not in WEAPON_TYPES:
            continue

        name = clean_name(item.get("name"))
        if not name:
            continue

        std = item.get("stdItem") or {}
        mfr = get_manufacturer(item)
        size = item.get("size")

        # If we already have a weapon with this name+size, reuse it so
        # that multiple className variants (fixed/gimbal/etc.) don't create
        # duplicate rows.  Still map every className so loadout refs work.
        dedup_key = (name, size)
        if dedup_key in weapon_seen:
            weapon_by_class[item["className"]] = weapon_seen[dedup_key]
            continue

        # weapon_type: use DescriptionData "Item Type" for a human-readable label
        desc = get_desc_data(item)
        weapon_type = desc.get("Item Type") or item.get("subType") or WEAPON_SUBTYPE_MAP.get(itype)

        # mount_type: look for it in classification or subtype
        # SC uses fixed/gimbal/turret distinction
        mount_type = None
        cls_str = item.get("classification", "")
        if "Gimbal" in cls_str or "gimbal" in (item.get("subType", "") or "").lower():
            mount_type = "gimbal"
        elif itype == "Turret":
            mount_type = "turret"

        # damage_type: not cleanly in this data; skip for now
        damage_type = None

        weapon = Weapon(
            name=name,
            weapon_type=weapon_type,
            size=size,
            mount_type=mount_type,
            damage_type=damage_type,
            manufacturer=mfr,
            stats=extract_stats(item, itype),
        )
        db.session.add(weapon)
        db.session.flush()

        weapon_by_class[item["className"]] = weapon
        weapon_seen[dedup_key] = weapon

    db.session.commit()
    log(f"  → {db.session.query(Weapon).count()} weapons")

    # ----------------------------------------------------------------
    # 5. Import ships + default loadouts
    # ----------------------------------------------------------------
    log("Importing ships …")
    ship_count = 0
    slot_count = 0
    ship_seen = set()  # deduplicate by name

    for raw in raw_ships:
        # Only actual spaceships
        if not raw.get("IsSpaceship"):
            continue

        name = clean_name(raw.get("Name"))
        if not name:
            continue

        if name in ship_seen:
            continue
        ship_seen.add(name)

        mfr_obj = raw.get("Manufacturer") or {}
        mfr = mfr_obj.get("Name") or None
        if mfr == "Unknown Manufacturer":
            mfr = None

        power_data = raw.get("Power") or {}
        fc = raw.get("FlightCharacteristics") or {}
        speeds = fc.get("Speeds") or {}
        angular = fc.get("AngularRates") or {}
        angular_boost = fc.get("AngularRatesBoosted") or {}
        accel_raw = fc.get("Acceleration", {}).get("Raw") or {}
        armor = raw.get("Armor") or {}
        dmg_mults = armor.get("DamageMultipliers") or {}
        insurance = raw.get("Insurance") or {}
        propulsion = raw.get("Propulsion") or {}
        qt = raw.get("QuantumTravel") or {}

        # Compute default missile damage from ship loadout
        default_missile_damage = 0
        for entry in raw.get("Loadout", []):
            entry_types = [it.get("Type", "") for it in entry.get("ItemTypes", [])]
            if "MissileLauncher" in entry_types:
                for sub in entry.get("Loadout", []):
                    sub_cn = sub.get("ClassName") or ""
                    if sub_cn in missile_damage_by_class:
                        default_missile_damage += missile_damage_by_class[sub_cn]

        ship_stats = {
            "ship_hp":         raw.get("Health"),
            "armor_hp":        armor.get("Health"),
            "scm_speed":       speeds.get("Scm"),
            "max_speed":       speeds.get("Max"),
            "pitch":           angular.get("Pitch"),
            "yaw":             angular.get("Yaw"),
            "roll":            angular.get("Roll"),
            "pitch_boosted":   angular_boost.get("Pitch"),
            "yaw_boosted":     angular_boost.get("Yaw"),
            "roll_boosted":    angular_boost.get("Roll"),
            "accel_forward":   accel_raw.get("Forward"),
            "accel_back":      accel_raw.get("Backward"),
            "accel_lateral":   accel_raw.get("Strafe"),
            "fuel_hydrogen":   propulsion.get("FuelCapacity"),
            "fuel_quantum":    qt.get("FuelCapacity"),
            "insurance_standard":       insurance.get("StandardClaimTime"),
            "insurance_expedited":      insurance.get("ExpeditedClaimTime"),
            "insurance_expedite_cost":  insurance.get("ExpeditedCost"),
            "dmg_mult_physical":    dmg_mults.get("Physical"),
            "dmg_mult_energy":      dmg_mults.get("Energy"),
            "dmg_mult_distortion":  dmg_mults.get("Distortion"),
            "dmg_mult_thermal":     dmg_mults.get("Thermal"),
            "missile_damage_default": default_missile_damage if default_missile_damage else None,
            "length":          raw.get("Length"),
            "width":           raw.get("Width"),
            "height":          raw.get("Height"),
        }
        ship = Ship(
            name=name,
            manufacturer=mfr,
            size_category=map_size_category(raw.get("Size")),
            crew_size=raw.get("Crew") or None,
            cargo_scu=raw.get("Cargo") or None,
            source_file="ships.json",
            power_generation_pips=power_data.get("GenerationSegments") or None,
            power_segments=power_data.get("UsedSegmentsGrouped") or None,
            ship_stats=ship_stats,
        )
        db.session.add(ship)
        db.session.flush()
        ship_count += 1

        # -- Parse loadout slots --
        slot_counters = {}  # slot_type → running count
        turret_groups  = {}  # turret ClassName → mount_group int
        turret_info    = {}  # turret ClassName → (mount_type, mount_label)
        turret_counter = 0

        for entry in raw.get("Loadout", []):
            entry_types = slot_types_from_entry(entry)
            class_name = entry.get("ClassName") or ""

            if any("Turret" in t for t in entry_types):
                is_gimbal = "Gimbal" in class_name

                if is_gimbal:
                    mount_t, mount_g, mount_lbl = "pilot", 0, None
                else:
                    if class_name not in turret_groups:
                        turret_counter += 1
                        turret_groups[class_name] = turret_counter
                        turret_info[class_name] = classify_turret(class_name)
                    mount_g = turret_groups[class_name]
                    mount_t, mount_lbl = turret_info[class_name]

                for gun_size, gun_class in iter_gun_slots(entry):
                    slot_counters["weapon"] = slot_counters.get("weapon", 0) + 1
                    default_weapon_id = None
                    if gun_class and gun_class in weapon_by_class:
                        default_weapon_id = weapon_by_class[gun_class].id
                    db.session.add(ShipDefaultLoadout(
                        ship_id=ship.id,
                        slot_type="weapon",
                        slot_number=slot_counters["weapon"],
                        slot_size=gun_size,
                        default_component_id=None,
                        default_weapon_id=default_weapon_id,
                        mount_type=mount_t,
                        mount_group=mount_g,
                        mount_label=mount_lbl,
                    ))
                    slot_count += 1
                continue

            # Non-mount: match against SLOT_TYPE_MAP normally
            matched_slot_type = None
            for et in entry_types:
                if et in SLOT_TYPE_MAP:
                    matched_slot_type = et
                    break

            if not matched_slot_type:
                continue

            # Skip bomb/missile launchers that also report WeaponGun — they are
            # not gun hardpoints (e.g. C2 Hercules belly-ramp S10 BombLauncher entries).
            if matched_slot_type == "WeaponGun" and any(
                t in entry_types for t in ("BombLauncher", "MissileLauncher")
            ):
                continue

            db_slot_type = SLOT_TYPE_MAP[matched_slot_type]
            slot_counters[db_slot_type] = slot_counters.get(db_slot_type, 0) + 1
            slot_number = slot_counters[db_slot_type]

            default_component_id = None
            default_weapon_id = None

            if db_slot_type != "weapon":
                if class_name and class_name in component_by_class:
                    default_component_id = component_by_class[class_name].id
            else:
                if class_name and class_name in weapon_by_class:
                    default_weapon_id = weapon_by_class[class_name].id

            # If scunpacked reports slot_size=0 but we know the default component,
            # infer the slot size from the component (skips S0 bespoke components).
            raw_size = entry.get("MaxSize") or 0
            if raw_size == 0 and default_component_id:
                comp_obj = component_by_class.get(class_name)
                if comp_obj and comp_obj.size:
                    raw_size = comp_obj.size

            db.session.add(ShipDefaultLoadout(
                ship_id=ship.id,
                slot_type=db_slot_type,
                slot_number=slot_number,
                slot_size=raw_size,
                default_component_id=default_component_id,
                default_weapon_id=default_weapon_id,
                mount_type="pilot" if db_slot_type == "weapon" else None,
                mount_group=0 if db_slot_type == "weapon" else None,
                mount_label=None,
            ))
            slot_count += 1

        # -- Apply manual slot overrides for this ship --
        override = ship_slot_overrides.get(name)
        if override:
            for extra in override.get("add_slots", []):
                stype = extra["slot_type"]
                slot_counters[stype] = slot_counters.get(stype, 0) + 1
                # Resolve default component by name+type+size
                default_component_id = None
                comp_name = extra.get("default_component")
                if comp_name:
                    itype_map = {v: k for k, v in COMPONENT_TYPE_MAP.items()}
                    itype_key = itype_map.get(stype)
                    lookup_key = (comp_name, stype, extra.get("slot_size"), None)
                    # Try with any grade (grade may vary; just match name+type+size)
                    matched = next(
                        (c for key, c in component_seen.items()
                         if key[0] == comp_name and key[1] == stype and key[2] == extra.get("slot_size")),
                        None
                    )
                    if matched:
                        default_component_id = matched.id
                db.session.add(ShipDefaultLoadout(
                    ship_id=ship.id,
                    slot_type=stype,
                    slot_number=slot_counters[stype],
                    slot_size=extra.get("slot_size"),
                    default_component_id=default_component_id,
                    default_weapon_id=None,
                    mount_type=None,
                    mount_group=None,
                    mount_label=None,
                ))
                slot_count += 1

            # modify_slots: patch attributes of existing slots by slot_type+slot_number
            for patch in override.get("modify_slots", []):
                target = db.session.query(ShipDefaultLoadout).filter_by(
                    ship_id=ship.id,
                    slot_type=patch["slot_type"],
                    slot_number=patch["slot_number"],
                ).first()
                if target:
                    if "slot_size" in patch:
                        target.slot_size = patch["slot_size"]
                    if "default_component" in patch:
                        new_size = patch.get("slot_size") or target.slot_size
                        matched = next(
                            (c for key, c in component_seen.items()
                             if key[0] == patch["default_component"] and key[1] == patch["slot_type"] and key[2] == new_size),
                            None
                        )
                        target.default_component_id = matched.id if matched else None

            # delete_slots: remove spurious slots created by scunpacked data
            for patch in override.get("delete_slots", []):
                target = db.session.query(ShipDefaultLoadout).filter_by(
                    ship_id=ship.id,
                    slot_type=patch["slot_type"],
                    slot_number=patch["slot_number"],
                ).first()
                if target:
                    db.session.delete(target)

    db.session.commit()
    log(f"  → {ship_count} ships, {slot_count} loadout slots")

    # ----------------------------------------------------------------
    # 5b. Apply ship data overrides (stat corrections)
    # ----------------------------------------------------------------
    data_overrides_path = DEFAULT_DATA_OVERRIDES_JSON
    if os.path.exists(data_overrides_path):
        with open(data_overrides_path, encoding="utf-8") as f:
            raw_data_overrides = json.load(f)
        ship_data_overrides = {k: v for k, v in raw_data_overrides.items() if not k.startswith("_")}
        for ship_name, patches in ship_data_overrides.items():
            ship = db.session.query(Ship).filter_by(name=ship_name).first()
            if ship:
                for field, value in patches.items():
                    if field == "note":
                        continue
                    if hasattr(ship, field):
                        setattr(ship, field, value)
        db.session.commit()

    # ----------------------------------------------------------------
    # 6. Sync existing user loadouts to updated reference data
    # ----------------------------------------------------------------
    log("Syncing user loadouts …")
    synced = 0
    for my_ship in db.session.query(MyShip).all():
        defaults = {
            (d.slot_type, d.slot_number): d
            for d in db.session.query(ShipDefaultLoadout).filter_by(ship_id=my_ship.ship_id).all()
        }
        user_slots = {(s.slot_type, s.slot_number): s for s in my_ship.loadout}

        # Fix stale IDs and add missing slots
        for (stype, snum), default in defaults.items():
            if (stype, snum) in user_slots:
                slot = user_slots[(stype, snum)]
                # Always reset weapons to the current default — slot structure changes
                # frequently during import development and user customization is minimal.
                if stype == "weapon" and slot.weapon_id != default.default_weapon_id:
                    slot.weapon_id = default.default_weapon_id
                    synced += 1
                elif slot.weapon_id and not db.session.get(Weapon, slot.weapon_id):
                    slot.weapon_id = default.default_weapon_id
                    synced += 1
                if slot.component_id and not db.session.get(Component, slot.component_id):
                    slot.component_id = default.default_component_id
                    synced += 1
            else:
                db.session.add(MyShipLoadout(
                    my_ship_id=my_ship.id,
                    slot_type=stype,
                    slot_number=snum,
                    component_id=default.default_component_id,
                    weapon_id=default.default_weapon_id,
                ))
                synced += 1

        # Remove slots that no longer exist in the default loadout
        for (stype, snum), slot in user_slots.items():
            if (stype, snum) not in defaults:
                db.session.delete(slot)
                synced += 1

    db.session.commit()
    log(f"  → {synced} user loadout entries synced")

    # ----------------------------------------------------------------
    # 7. Summary
    # ----------------------------------------------------------------
    summary = {
        "ships": db.session.query(Ship).count(),
        "components": db.session.query(Component).count(),
        "weapons": db.session.query(Weapon).count(),
        "slots": db.session.query(ShipDefaultLoadout).count(),
    }
    log(f"\n=== Import complete ===")
    log(f"  Ships:         {summary['ships']}")
    log(f"  Components:    {summary['components']}")
    log(f"  Weapons:       {summary['weapons']}")
    log(f"  Loadout slots: {summary['slots']}")
    return summary


def run_import(ships_path, items_path):
    """CLI entry point — creates its own app context."""
    app = create_app()
    with app.app_context():
        return do_import(ships_path, items_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import scunpacked-data into SCCT DB")
    parser.add_argument("--ships", default=DEFAULT_SHIPS_JSON, help="Path to ships.json")
    parser.add_argument("--items", default=DEFAULT_ITEMS_JSON, help="Path to ship-items.json")
    args = parser.parse_args()

    ships_path = os.path.abspath(args.ships)
    items_path = os.path.abspath(args.items)

    if not os.path.exists(ships_path):
        print(f"ERROR: ships.json not found at {ships_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(items_path):
        print(f"ERROR: ship-items.json not found at {items_path}", file=sys.stderr)
        sys.exit(1)

    run_import(ships_path, items_path)
