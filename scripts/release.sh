#!/usr/bin/env bash
# Usage: bump data/version.txt, then run: bash scripts/release.sh
#
# This script does NOT build the exe locally. It commits the version bump,
# pushes main, and pushes a version tag. The tag push triggers
# .github/workflows/build-release.yml, which builds SCCT.exe with the pinned
# CI Python (3.12) and publishes the GitHub release.
#
# Why not build locally: the local venv-win is Python 3.14, which produces an
# exe that needs a newer MS Visual C++ runtime than most users have ("Failed to
# load the Python DLL"). Building locally AND letting the tag trigger CI also
# created a race where the bad local exe was briefly the published asset before
# CI clobbered it. Letting CI own the build removes both problems.

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
GH="/c/Program Files/GitHub CLI/gh.exe"

VERSION=$(tr -d '[:space:]' < "${REPO_DIR}/data/version.txt")
if [ -z "$VERSION" ]; then
  echo "ERROR: Could not read version from data/version.txt" >&2
  exit 1
fi
TAG="v${VERSION}"

# --- Safety checks --------------------------------------------------------
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
  echo "ERROR: not on main (on '$BRANCH'). Switch to main before releasing." >&2
  exit 1
fi

echo "==> Fetching origin..."
git fetch origin --quiet

# Refuse to release if origin/main has commits we don't have (e.g. the 06:00
# UTC auto-data cron pushed a patch bump). Otherwise our push fails and/or our
# version number collides with the cron's.
BASE=$(git merge-base HEAD origin/main)
REMOTE_MAIN=$(git rev-parse origin/main)
if [ "$REMOTE_MAIN" != "$BASE" ]; then
  echo "ERROR: origin/main is ahead of your local main (the auto-data cron may have" >&2
  echo "       pushed). Run:  git pull --rebase origin main" >&2
  echo "       then re-check/bump data/version.txt above origin's, and retry." >&2
  exit 1
fi

# Tag must not already exist locally or on origin.
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  echo "ERROR: tag ${TAG} already exists locally. Bump data/version.txt." >&2
  exit 1
fi
if git ls-remote --exit-code --tags origin "${TAG}" >/dev/null 2>&1; then
  echo "ERROR: tag ${TAG} already exists on origin. Bump data/version.txt above it." >&2
  exit 1
fi

# --- Sync + commit the version bump --------------------------------------
# Keep the dev-mode root version.txt in step with the packaged data/version.txt.
printf '%s\n' "$VERSION" > "${REPO_DIR}/version.txt"

if ! git diff --quiet -- data/version.txt version.txt; then
  git add data/version.txt version.txt
  git commit -m "chore: bump version to ${VERSION}"
fi

# CI builds from the pushed commit, so anything left uncommitted would silently
# NOT ship. Refuse to proceed with a dirty tree.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree has uncommitted changes beyond the version files." >&2
  echo "       Commit or stash them so CI builds a clean tree, then re-run." >&2
  git status --short >&2
  exit 1
fi

# --- Push main, then the tag (triggers Build & Release, Python 3.12) -------
echo "==> Pushing main..."
git push origin main

echo "==> Pushing tag ${TAG}..."
git tag -a "${TAG}" -m "SCCT-DB ${TAG}"
git push origin "${TAG}"

echo ""
echo "Tag pushed — CI is building and publishing the release."
echo "  Actions:  https://github.com/Lucky44/SCCT-DB/actions/workflows/build-release.yml"
echo "  Release:  https://github.com/Lucky44/SCCT-DB/releases/tag/${TAG}"

# --- Best-effort: stream the CI run so you see success/failure here --------
if [ -x "$GH" ]; then
  echo ""
  echo "==> Locating the workflow run..."
  RUN_ID=""
  for _ in 1 2 3 4 5 6; do
    RUN_ID=$("$GH" run list --workflow build-release.yml --branch "${TAG}" \
              --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
    [ -n "$RUN_ID" ] && break
    sleep 5
  done
  if [ -n "$RUN_ID" ]; then
    "$GH" run watch "$RUN_ID" --exit-status \
      && echo "Done! Release published: https://github.com/Lucky44/SCCT-DB/releases/tag/${TAG}" \
      || echo "WARNING: the build workflow did not succeed — check the Actions tab above."
  else
    echo "NOTE: couldn't locate the run automatically; check the Actions tab above."
  fi
fi
