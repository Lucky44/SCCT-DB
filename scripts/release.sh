#!/usr/bin/env bash
# Usage: bash scripts/release.sh
# Builds dist/SCCT.exe via Windows pyinstaller and publishes a GitHub release.
# Version is read automatically from app/templates/base.html.

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WIN_REPO="C:\\Users\\tripp\\projects\\SCCT-DB"

# Detect version from navbar
VERSION=$(grep -oE 'v[0-9]+\.[0-9]+' "${REPO_DIR}/app/templates/base.html" | head -1 | sed 's/v//')
if [ -z "$VERSION" ]; then
  echo "ERROR: Could not detect version from base.html" >&2
  exit 1
fi
TAG="v${VERSION}"
echo "==> Building SCCT ${TAG}..."

# Kill any running SCCT instance
powershell.exe -Command "Stop-Process -Name 'SCCT' -Force -ErrorAction SilentlyContinue" 2>/dev/null || true

# Build with pyinstaller using the Windows venv
powershell.exe -Command "
  Set-Location '${WIN_REPO}';
  & '${WIN_REPO}\\venv-win\\Scripts\\pyinstaller.exe' \`
    --onefile --noconsole \`
    --add-data 'app/templates;app/templates' \`
    --add-data 'app/static;app/static' \`
    --add-data 'data;data' \`
    --hidden-import waitress \`
    --name SCCT run_packaged.py
"

EXE="${REPO_DIR}/dist/SCCT.exe"
if [ ! -f "$EXE" ]; then
  echo "ERROR: dist/SCCT.exe not found — build may have failed" >&2
  exit 1
fi

echo "==> Creating GitHub release ${TAG}..."
GH="${PROGRAMFILES}/GitHub CLI/gh.exe"
WIN_EXE="${WIN_REPO}\\dist\\SCCT.exe"
powershell.exe -Command "& '${GH}' release create '${TAG}' '${WIN_EXE}#SCCT.exe' --title 'SCCT-DB ${TAG}' --notes 'Release ${TAG}' --latest"

echo ""
echo "Done! Latest release: https://github.com/Lucky44/SCCT-DB/releases/latest"
