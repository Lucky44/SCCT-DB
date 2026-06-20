"""
Update checker and auto-updater for SCCT.

Flow:
  1. check_for_update()  — hits GitHub API, cached 1hr
  2. download_update()   — downloads new exe as SCCT_update.exe next to current exe
  3. launch_update_and_exit() — writes a swap batch script, launches it detached, exits app

Only functional when running as a PyInstaller exe (sys.frozen).
In dev mode, check_for_update() still works but download/restart return errors.
"""

import os
import sys
import json
import time
import urllib.request

REPO       = "Lucky44/SCCT-DB"
GITHUB_API = f"https://api.github.com/repos/{REPO}/releases/latest"
UPDATE_EXE = "SCCT_update.exe"
CACHE_TTL  = 3600   # seconds — re-check at most once per hour

_cache: dict = {"checked_at": 0.0, "result": None}


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def _version_file_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "data", "version.txt")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "version.txt")


def get_current_version() -> str:
    """Return bundled version string, e.g. '0.71.0'."""
    try:
        with open(_version_file_path(), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _as_tuple(v: str) -> tuple:
    """'v0.71.3' → (0, 71, 3)"""
    v = v.lstrip("v").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0, 0, 0)


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

def check_for_update(force: bool = False) -> dict:
    """
    Check GitHub for a newer release. Result is cached for CACHE_TTL seconds.
    Returns a dict with keys:
        update_available  bool
        current_version   str
        latest_version    str
        download_url      str | None  (direct link to .exe asset)
        release_url       str         (GitHub releases page)
        error             str | None
    """
    global _cache
    now = time.time()

    if not force and _cache["result"] and (now - _cache["checked_at"]) < CACHE_TTL:
        return _cache["result"]

    current = get_current_version()
    result = {
        "update_available": False,
        "current_version":  current,
        "latest_version":   current,
        "download_url":     None,
        "release_url":      f"https://github.com/{REPO}/releases/latest",
        "error":            None,
    }

    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                "User-Agent": "SCCT-UpdateChecker/1.0",
                "Accept":     "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag        = data.get("tag_name", "")
        latest_ver = tag.lstrip("v")
        result["latest_version"] = latest_ver

        for asset in data.get("assets", []):
            if asset.get("name", "").lower().endswith(".exe"):
                result["download_url"] = asset["browser_download_url"]
                break

        if _as_tuple(latest_ver) > _as_tuple(current):
            result["update_available"] = True

    except Exception as exc:
        result["error"] = str(exc)

    _cache = {"checked_at": now, "result": result}
    return result


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def get_exe_dir() -> str | None:
    """Return directory of the running exe; None when running from source."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return None


def download_update(download_url: str) -> dict:
    """
    Stream-download the new exe to SCCT_update.exe next to the current exe.
    Blocks until complete. Returns {ok, error}.
    """
    exe_dir = get_exe_dir()
    if not exe_dir:
        return {"ok": False, "error": "Auto-download only works in the packaged exe."}

    dest = os.path.join(exe_dir, UPDATE_EXE)
    tmp_dest = dest + ".tmp"
    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "SCCT-UpdateChecker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.getcode()
            if status != 200:
                return {"ok": False, "error": f"HTTP {status} from download URL."}

            content_length = resp.headers.get("Content-Length")
            expected_bytes = int(content_length) if content_length else None

            with open(tmp_dest, "wb") as f:
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

        # Verify size if server provided Content-Length
        if expected_bytes and downloaded != expected_bytes:
            os.remove(tmp_dest)
            return {"ok": False, "error": f"Download incomplete: got {downloaded} of {expected_bytes} bytes."}

        # Verify PE magic bytes (MZ header) — catches HTML error pages saved as .exe
        with open(tmp_dest, "rb") as f:
            magic = f.read(2)
        if magic != b"MZ":
            os.remove(tmp_dest)
            return {"ok": False, "error": "Downloaded file is not a valid executable (bad magic bytes)."}

        # Atomically replace any previous update file
        if os.path.exists(dest):
            os.remove(dest)
        os.rename(tmp_dest, dest)
        return {"ok": True}
    except Exception as exc:
        if os.path.exists(tmp_dest):
            os.remove(tmp_dest)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Swap & restart
# ---------------------------------------------------------------------------

def launch_update_and_exit() -> None:
    """
    Write a small Windows batch script that:
      1. Waits 2 s for the current process to fully exit
      2. Deletes the old exe
      3. Renames SCCT_update.exe → SCCT.exe
      4. Launches the new exe
      5. Self-deletes

    Then launches the script detached and exits this process immediately.
    Only works in packaged (frozen) mode.
    """
    import subprocess

    exe_dir  = get_exe_dir()
    if not exe_dir:
        return

    exe_path = sys.executable
    exe_name = os.path.basename(exe_path)
    new_exe  = os.path.join(exe_dir, UPDATE_EXE)
    bat_path = os.path.join(exe_dir, "_scct_update.bat")

    bat = (
        "@echo off\n"
        "timeout /t 2 /nobreak > nul\n"
        f'del "{exe_path}"\n'
        f'rename "{new_exe}" "{exe_name}"\n'
        f'start "" "{exe_path}"\n'
        'del "%~f0"\n'
    )
    with open(bat_path, "w") as f:
        f.write(bat)

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    time.sleep(0.5)
    os._exit(0)
