"""
Audit ShipDefaultLoadout data for common scunpacked data quality issues.

Checks performed:
  1. Component slots with slot_size=0 or None  (causes unfiltered slot picker)
  2. Default component size != slot size        (wrong component assigned)
  3. Ships with >2 of any component type        (suspicious; may have spurious slots)
  4. Ships with 0 quantum_drive slots           (almost every spaceship needs one)
  5. Slot number gaps within a type            (e.g., slot 1 then slot 3, no slot 2)
  6. Component slots with no default component  (will show as EMPTY after add-to-fleet)

Usage:
    venv/bin/python scripts/audit_slots.py [--ship NAME]

    --ship NAME   filter output to a single ship (partial match, case-insensitive)
"""

import sys
import os
import argparse
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db
from app.models import Ship, ShipDefaultLoadout, Component

COMPONENT_SLOT_TYPES = {"power_plant", "cooler", "shield_generator", "quantum_drive"}

# Ships known to legitimately lack a QD (snub fighters, in-system-only utility craft)
NO_QD_EXCEPTIONS = {
    "Kruger P-52 Merlin",
    "Kruger P-72 Archimedes",
    "Kruger P-72 Archimedes Emerald",
    "Mirai Fury",
    "Mirai Fury LX",
    "Mirai Fury MX",
    "Argo MPUV Cargo",
    "Argo MPUV Personnel",
    "Argo MPUV Tractor",
}

# Expected max slot counts — anything above this gets flagged
MAX_NORMAL = {
    "power_plant":      2,
    "cooler":           3,
    "shield_generator": 2,
    "quantum_drive":    1,
}


def run_audit(ship_filter=None):
    issues = []

    ships = db.session.query(Ship).order_by(Ship.name).all()
    if ship_filter:
        ships = [s for s in ships if ship_filter.lower() in s.name.lower()]

    for ship in ships:
        slots = (
            db.session.query(ShipDefaultLoadout)
            .filter_by(ship_id=ship.id)
            .order_by(ShipDefaultLoadout.slot_type, ShipDefaultLoadout.slot_number)
            .all()
        )

        # Group by type
        by_type = defaultdict(list)
        for slot in slots:
            by_type[slot.slot_type].append(slot)

        for stype in COMPONENT_SLOT_TYPES:
            type_slots = by_type.get(stype, [])

            # Check 4: missing QD
            if stype == "quantum_drive" and not type_slots and ship.name not in NO_QD_EXCEPTIONS:
                issues.append((ship.name, "quantum_drive", None,
                    "NO quantum_drive slot — ship may be missing QD hardpoint"))
                continue

            for slot in type_slots:
                label = f"{stype} slot#{slot.slot_number}"

                # Check 1: slot_size=0 or None
                if not slot.slot_size:
                    issues.append((ship.name, label, slot,
                        f"slot_size={slot.slot_size!r} — picker will show all sizes"))

                # Check 2: default component size mismatch
                if slot.default_component_id and slot.slot_size:
                    comp = db.session.get(Component, slot.default_component_id)
                    if comp and comp.size != slot.slot_size:
                        issues.append((ship.name, label, slot,
                            f"default component '{comp.name}' is S{comp.size} but slot is S{slot.slot_size}"))

                # Check 6: no default component
                if slot.slot_size and not slot.default_component_id:
                    issues.append((ship.name, label, slot,
                        "no default component — slot will be EMPTY after add-to-fleet"))

            # Check 3: suspicious slot count
            max_ok = MAX_NORMAL.get(stype, 99)
            if len(type_slots) > max_ok:
                issues.append((ship.name, stype, None,
                    f"{len(type_slots)} slots (expected ≤{max_ok}) — possible spurious slot"))

            # Check 5: slot number gaps
            nums = sorted(s.slot_number for s in type_slots)
            expected = list(range(1, len(nums) + 1))
            if nums != expected:
                issues.append((ship.name, stype, None,
                    f"slot numbers {nums} are not sequential (expected {expected})"))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Audit slot data for common scunpacked issues")
    parser.add_argument("--ship", help="Filter to a single ship (partial name match)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        issues = run_audit(ship_filter=args.ship)

    if not issues:
        print("No issues found.")
        return

    current_ship = None
    for ship_name, slot_label, slot_obj, msg in issues:
        if ship_name != current_ship:
            print(f"\n{'='*60}")
            print(f"  {ship_name}")
            print(f"{'='*60}")
            current_ship = ship_name
        size_str = f" (S{slot_obj.slot_size})" if slot_obj and slot_obj.slot_size else ""
        print(f"  [{slot_label}{size_str}]  {msg}")

    print(f"\n{len(issues)} issue(s) found across {len({i[0] for i in issues})} ship(s).")


if __name__ == "__main__":
    main()
