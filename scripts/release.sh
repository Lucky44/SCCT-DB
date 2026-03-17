#!/usr/bin/env bash
# Usage: bash scripts/release.sh
# Builds dist/SCCT.exe via Windows pyinstaller and publishes a GitHub release.
# Version is read automatically from app/templates/base.html.

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WIN_REPO="C:\\Users\\tripp\\projects\\SCCT-DB"

# Read version from data/version.txt
VERSION=$(cat "${REPO_DIR}/data/version.txt" | tr -d '[:space:]')
if [ -z "$VERSION" ]; then
  echo "ERROR: Could not read version from data/version.txt" >&2
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
    --add-data 'scripts;scripts' \`
    --hidden-import waitress \`
    --name SCCT run_packaged.py
"

EXE="${REPO_DIR}/dist/SCCT.exe"
if [ ! -f "$EXE" ]; then
  echo "ERROR: dist/SCCT.exe not found — build may have failed" >&2
  exit 1
fi

echo "==> Creating GitHub release ${TAG}..."
WIN_EXE="${WIN_REPO}\\dist\\SCCT.exe"
powershell.exe -Command "
  gh release create '${TAG}' '${WIN_EXE}#SCCT.exe' --title 'SCCT-DB ${TAG}' --notes 'Release ${TAG}' --latest 2>\$null
  if (\$LASTEXITCODE -ne 0) {
    Write-Host 'Release exists — replacing exe asset...'
    gh release upload '${TAG}' '${WIN_EXE}#SCCT.exe' --clobber
  }
"

echo ""
echo "Done! Latest release: https://github.com/Lucky44/SCCT-DB/releases/latest"
