"""
Fetch component data from the erkul.games PTU API and save to data/erkul_data.json.

This script is the first step in the automated update pipeline:
  1. Run this script to pull fresh data from erkul
  2. Run import_scunpacked.py to import into the DB (it reads erkul_data.json automatically)
  3. GitHub Actions runs both on a schedule and builds a new exe if data changed

Usage:
    python scripts/fetch_erkul_data.py [--live] [--check-only] [--out PATH]

Options:
    --live        Use erkul live data instead of PTU
    --check-only  Exit 0 if data unchanged, exit 1 if changed (used by CI to decide whether to rebuild)
    --out PATH    Output file path (default: data/erkul_data.json)
"""

import sys
import os
import json
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "data", "erkul_data.json")

ERKUL_BASE = "https://server.erkul.games"
ERKUL_HEADERS = {
    "Origin": "https://erkul.games",
    "User-Agent": "SCCT-DataFetcher/1.0",
}

# ---------------------------------------------------------------------------
# Endpoint config: (url_path, calculatorType)
# ---------------------------------------------------------------------------
ENDPOINTS = {
    "cooler":           "coolers",
    "power_plant":      "power-plants",   # hyphenated — not "powerplants"
    "shield_generator": "shields",
    "quantum_drive":    "qdrives",        # abbreviated — not "quantumdrives"
    "radar":            "radars",
}


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> list:
    req = urllib.request.Request(url, headers=ERKUL_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Stat extractors — one per component type
# All return a flat dict using the same keys as Component.stats in the DB
# ---------------------------------------------------------------------------

def _power_min(resource_online: dict) -> int | None:
    """Best-effort power pip minimum from erkul's powerRanges structure."""
    ranges = resource_online.get("powerRanges")
    if isinstance(ranges, list) and ranges:
        return ranges[0].get("start")
    if isinstance(ranges, dict):
        # Dict form uses low/medium/high keys; find lowest non-zero start
        for key in ("low", "medium", "high"):
            entry = ranges.get(key, {})
            start = entry.get("start")
            if start is not None and start > 0:
                return start
        return 1  # minimum 1 if all starts are 0
    return None


def _distortion_stats(data: dict) -> dict:
    d = data.get("distortion", {})
    return {
        "distortion_shutdown_damage": d.get("maximum"),
        "distortion_decay_delay":     d.get("decayDelay"),
        "distortion_decay_rate":      d.get("decayRate"),
        "distortion_recovery_ratio":  d.get("recoveryRatio"),
        "distortion_warning_ratio":   d.get("warningRatio"),
    }


def extract_cooler_stats(data: dict) -> dict:
    online   = data.get("resource", {}).get("online", {})
    sigs     = online.get("signatureParams", {})
    return {
        "cooling_generation":  online.get("generation", {}).get("cooling"),
        "power_pips_max":      online.get("consumption", {}).get("powerSegment"),
        "power_pips_min":      _power_min(online),
        "em_signature":        sigs.get("em", {}).get("nominalSignature"),
        "ir_signature":        sigs.get("ir", {}).get("nominalSignature"),
        "health":              data.get("health", {}).get("hp"),
        **_distortion_stats(data),
    }


def extract_power_plant_stats(data: dict) -> dict:
    online = data.get("resource", {}).get("online", {})
    sigs   = online.get("signatureParams", {})
    return {
        "power_generation": online.get("generation", {}).get("powerSegment"),
        "em_max":           sigs.get("em", {}).get("nominalSignature"),
        "health":           data.get("health", {}).get("hp"),
        **_distortion_stats(data),
    }


def extract_shield_stats(data: dict) -> dict:
    shield = data.get("shield", {})
    online = data.get("resource", {}).get("online", {})
    sigs   = online.get("signatureParams", {})
    return {
        "shield_hp":            shield.get("maxShieldHealth"),
        "shield_regen":         shield.get("maxShieldRegen"),
        "regen_delay_damaged":  shield.get("damagedRegenDelay"),
        "regen_delay_downed":   shield.get("downedRegenDelay"),
        "power_pips_max":       online.get("consumption", {}).get("powerSegment"),
        "power_pips_min":       _power_min(online),
        "em_signature":         sigs.get("em", {}).get("nominalSignature"),
        "ir_signature":         sigs.get("ir", {}).get("nominalSignature"),
        "health":               data.get("health", {}).get("hp"),
        **_distortion_stats(data),
    }


def extract_qdrive_stats(data: dict) -> dict:
    qd     = data.get("qdrive", {})
    params = qd.get("params", {})
    online = data.get("resource", {}).get("online", {})
    travel = data.get("resource", {}).get("traveling", {})
    return {
        "spool_time":        params.get("spoolUpTime"),
        "cooldown":          params.get("cooldownTime"),
        "drive_speed":       params.get("driveSpeed"),
        "fuel_requirement":  qd.get("quantumFuelRequirement"),
        "power_pips_min":    online.get("consumption", {}).get("power"),
        "power_pips_max":    travel.get("consumption", {}).get("power"),
        "health":            data.get("health", {}).get("hp"),
    }


def extract_radar_stats(data: dict) -> dict:
    # NOTE: "signatureDtection" is a typo in the erkul API — the 'e' is missing
    radar  = data.get("radar", {})
    detect = radar.get("signatureDtection", {})
    return {
        "sensitivity_ir": detect.get("ir", {}).get("sensitivity"),
        "sensitivity_em": detect.get("em", {}).get("sensitivity"),
        "sensitivity_cs": detect.get("cs", {}).get("sensitivity"),
        "sensitivity_rs": detect.get("rs", {}).get("sensitivity"),
        "health":         data.get("health", {}).get("hp"),
        **_distortion_stats(data),
    }


STAT_EXTRACTORS = {
    "cooler":           extract_cooler_stats,
    "power_plant":      extract_power_plant_stats,
    "shield_generator": extract_shield_stats,
    "quantum_drive":    extract_qdrive_stats,
    "radar":            extract_radar_stats,
}


# ---------------------------------------------------------------------------
# Manufacturer extraction
# ---------------------------------------------------------------------------

def get_manufacturer(data: dict) -> str | None:
    mfr = data.get("manufacturerData", {})
    name = mfr.get("name") or mfr.get("nameSmall")
    if name and name not in ("Unknown Manufacturer", ""):
        return name
    return None


# ---------------------------------------------------------------------------
# Main fetch
# ---------------------------------------------------------------------------

def fetch_all(channel: str = "ptu", log=print) -> list:
    """
    Fetch all component types from erkul and return a normalized list of dicts.
    channel: "ptu" or "live"
    """
    components = []

    for comp_type, endpoint in ENDPOINTS.items():
        url = f"{ERKUL_BASE}/{channel}/{endpoint}"
        log(f"  Fetching {comp_type} from {url} …")
        try:
            items = fetch_json(url)
        except Exception:
            log(f"  WARNING: skipping {comp_type} (fetch failed)")
            continue

        extractor = STAT_EXTRACTORS[comp_type]
        count = 0

        for item in items:
            data = item.get("data", {})
            name = (data.get("name") or "").strip()

            # Skip placeholders and unnamed items
            if not name or "<=" in name:
                continue

            grade = data.get("grade")
            if isinstance(grade, int):
                # Convert numeric grade to letter (1=A, 2=B, 3=C, 4=D)
                grade = {1: "A", 2: "B", 3: "C", 4: "D"}.get(grade, str(grade))

            class_ = (data.get("class") or "").lower() or None

            components.append({
                "name":         name,
                "type":         comp_type,
                "size":         data.get("size"),
                "grade":        grade,
                "class_":       class_,
                "manufacturer": get_manufacturer(data),
                "local_name":   item.get("localName", ""),
                "stats":        extractor(data),
            })
            count += 1

        log(f"    → {count} {comp_type}s")

    return components


def content_hash(components: list) -> str:
    """Stable SHA-256 of the components list, for change detection."""
    serialized = json.dumps(components, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def run(channel: str = "ptu", out_path: str = DEFAULT_OUT,
        check_only: bool = False, log=print) -> bool:
    """
    Fetch, save, return True if data changed vs existing file.
    """
    log(f"Fetching erkul {channel.upper()} data …")
    components = fetch_all(channel, log=log)

    new_hash = content_hash(components)

    # Compare against existing file
    changed = True
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        old_hash = existing.get("metadata", {}).get("content_hash", "")
        changed = (new_hash != old_hash)

    if check_only:
        log(f"Data {'CHANGED' if changed else 'UNCHANGED'} (hash: {new_hash[:12]}…)")
        return changed

    output = {
        "metadata": {
            "fetched_at":    datetime.now(timezone.utc).isoformat(),
            "source":        f"server.erkul.games/{channel} API",
            "channel":       channel,
            "content_hash":  new_hash,
            "component_count": len(components),
        },
        "components": components,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    status = "CHANGED" if changed else "UNCHANGED"
    log(f"\n=== erkul fetch complete ({status}) ===")
    log(f"  Components: {len(components)}")
    log(f"  Hash:       {new_hash[:16]}…")
    log(f"  Saved to:   {out_path}")

    return changed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch erkul.games component data")
    parser.add_argument("--live",       action="store_true", help="Use live data instead of PTU")
    parser.add_argument("--check-only", action="store_true", help="Exit 1 if data changed, 0 if unchanged")
    parser.add_argument("--out",        default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()

    channel = "live" if args.live else "ptu"
    changed = run(channel=channel, out_path=args.out, check_only=args.check_only)

    if args.check_only:
        sys.exit(1 if changed else 0)
