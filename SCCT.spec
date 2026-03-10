# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SCCT (SC Component Tracker).

Build steps:
    1. python prepare_build.py          # copies ships.json + ship-items.json to data/
    2. venv/bin/pyinstaller SCCT.spec   # builds the exe
"""

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Flask templates and static assets
        ("app/templates",   "app/templates"),
        ("app/static",      "app/static"),
        # DB migrations
        ("migrations",      "migrations"),
        # Bundled game data (ships.json, ship-items.json)
        ("data",            "data"),
        # Import/image scripts (called at runtime)
        ("scripts",         "scripts"),
    ],
    hiddenimports=[
        "flask_migrate",
        "flask_sqlalchemy",
        "sqlalchemy",
        "alembic",
        "jinja2",
        "werkzeug",
        "requests",
        "click",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SCCT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # keep console visible so users can see first-run progress
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SCCT",
)
