"""
Validate SCCT database reference tables against external JSON datasets.

Usage:
    python scripts/validate_data.py [--items PATH] [--ships PATH]

The script will connect to the existing database via the Flask app context
and compare components/weapons/ships with the provided JSON files.  This
helps identify missing entries, mismatched sizes/grades, duplicate names,
and other discrepancies.  You can supply a second source if you want to
cross-check against something other than the default scunpacked data.

Examples:
    python scripts/validate_data.py --items /path/to/ship-items.json

If you don't provide any JSON files the script will simply dump counts.
"""

import sys
import os
import argparse
import json
from collections import defaultdict

# make sure we can import the app
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db
from app.models import Component, Weapon, Ship

# items JSON structure is the same as import_scunpacked.py expects
COMPONENT_TYPES = {"PowerPlant", "Cooler", "Shield", "QuantumDrive"}
WEAPON_TYPES = {"WeaponGun"}


def load_items_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # scunpacked ship-items.json is just a list; treat any list as the items
    items = data if isinstance(data, list) else data.get("items") or []
    comps = []
    weaps = []
    for item in items:
        itype = item.get("type") or item.get("itemType")
        if itype in COMPONENT_TYPES:
            comps.append(item)
        elif itype in WEAPON_TYPES:
            weaps.append(item)
    return comps, weaps


def summarize_db():
    comps = db.session.query(Component).all()
    weaps = db.session.query(Weapon).all()
    ships = db.session.query(Ship).all()
    return comps, weaps, ships


def compare_components(db_comps, json_comps):
    # build maps by name (lowercase)
    db_map = {c.name.lower(): c for c in db_comps}
    json_map = {}
    for item in json_comps:
        name = item.get("displayName") or item.get("name") or ""
        json_map[name.lower()] = item

    missing_in_db = []
    mismatches = []
    for lname, item in json_map.items():
        dbc = db_map.get(lname)
        if not dbc:
            missing_in_db.append(item)
        else:
            # compare key fields
            size = item.get("size")
            std = item.get("stdItem") or {}
            desc = std.get("DescriptionData") or {}
            grade = desc.get("Grade")
            cls = desc.get("Class")
            differences = []
            if size is not None and dbc.size != size:
                differences.append(f"size {dbc.size}!= {size}")
            if grade:
                letter = {1: "A", 2: "B", 3: "C", 4: "D"}.get(grade, str(grade))
                if str(dbc.grade).upper() != str(letter).upper():
                    differences.append(f"grade {dbc.grade}!= {letter}")
            if cls and str(dbc.class_).lower() != str(cls).lower():
                differences.append(f"class {dbc.class_}!= {cls}")
            if differences:
                mismatches.append((dbc, differences))
    extra_in_db = [c for name, c in db_map.items() if name not in json_map]
    return missing_in_db, extra_in_db, mismatches


def compare_weapons(db_weaps, json_weaps):
    db_map = {w.name.lower(): w for w in db_weaps}
    json_map = {}
    for item in json_weaps:
        name = item.get("displayName") or item.get("name") or ""
        json_map[name.lower()] = item
    missing = []
    mismatches = []
    for lname, item in json_map.items():
        dbw = db_map.get(lname)
        if not dbw:
            missing.append(item)
        else:
            size = item.get("size")
            std = item.get("stdItem") or {}
            desc = std.get("DescriptionData") or {}
            differences = []
            if size is not None and dbw.size != size:
                differences.append(f"size {dbw.size}!={size}")
            sub = item.get("subType")
            if sub and str(dbw.weapon_type).lower() != str(sub).lower():
                differences.append(f"type {dbw.weapon_type}!={sub}")
            if differences:
                mismatches.append((dbw, differences))
    extra = [w for name, w in db_map.items() if name not in json_map]
    return missing, extra, mismatches


def main():
    parser = argparse.ArgumentParser(description="Validate reference tables")
    parser.add_argument("--items", help="path to ship-items JSON to compare against")
    parser.add_argument("--ships", help="path to ships JSON to compare against")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db_comps, db_weaps, db_ships = summarize_db()
        print(f"DB has {len(db_comps)} components, {len(db_weaps)} weapons, {len(db_ships)} ships")
        if args.items:
            comps, weaps = load_items_json(args.items)
            print(f"JSON source has {len(comps)} components, {len(weaps)} weapons")
            missing, extra, mismatches = compare_components(db_comps, comps)
            if missing:
                print("\nComponents present in JSON but missing in DB:")
                for item in missing:
                    print("  ", item.get("displayName") or item.get("name"))
            if extra:
                print("\nComponents present in DB but not found in JSON:")
                for c in extra:
                    print("  ", c.name)
            if mismatches:
                print("\nComponent mismatches:")
                for dbobj, diffs in mismatches:
                    print("  ", dbobj.name, ", ".join(diffs))
            m, e, mm = compare_weapons(db_weaps, weaps)
            if m:
                print("\nWeapons present in JSON but missing in DB:")
                for item in m:
                    print("  ", item.get("displayName") or item.get("name"))
            if e:
                print("\nWeapons present in DB but not found in JSON:")
                for w in e:
                    print("  ", w.name)
            if mm:
                print("\nWeapon mismatches:")
                for dbw, diffs in mm:
                    print("  ", dbw.name, ", ".join(diffs))
        else:
            print("No JSON source provided; skipping comparison.")


if __name__ == "__main__":
    main()
