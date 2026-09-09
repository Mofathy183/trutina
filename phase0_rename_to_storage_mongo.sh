#!/usr/bin/env bash
#
# Phase 0 — rename trutina-infrastructure -> trutina-storage-mongo
#
# Run from the repo root, on a clean working tree (the script will refuse
# to run otherwise). Review `git diff --stat` after it finishes before
# committing — this is mechanical, not reviewed line-by-line by a human
# until you do it.
#
# What this does, in order:
#   1. git mv the package directory and flatten trutina/infrastructure/mongo/
#      into trutina/storage_mongo/ directly (no redundant nested mongo/).
#   2. Rewrite every `trutina.infrastructure.mongo` import to
#      `trutina.storage_mongo` (specific pattern first, so flattening is
#      correct rather than leaving a dangling `.mongo`).
#   3. Rewrite every remaining bare `trutina.infrastructure` reference
#      (import-linter layer names, prose in docs) to `trutina.storage_mongo`.
#   4. Rewrite every `trutina-infrastructure` (hyphenated distribution name)
#      to `trutina-storage-mongo`.
#   5. Patch conftest.py's _LAYER_DIRS entry, which is a bare string key,
#      not a `trutina.*` path, so steps 2-4 don't touch it.
#
# What this does NOT do (flagged as manual follow-ups at the end):
#   - conftest.py's docstring prose explaining _LAYER_DIRS by example.
#   - Cosmetic CI job key names / display names still saying "Infrastructure".
#   - Anything not caught by the grep patterns below (the script greps for
#     leftovers at the end and tells you if any remain).

set -euo pipefail

if [ ! -f pyproject.toml ] || ! grep -q 'tool.uv.workspace' pyproject.toml; then
  echo "Run this from the repo root (root pyproject.toml not found)." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean. Commit or stash before running this." >&2
  exit 1
fi

OLD_PKG_DIR="packages/infrastructure"
NEW_PKG_DIR="packages/storage-mongo"

if [ ! -d "$OLD_PKG_DIR" ]; then
  echo "Expected $OLD_PKG_DIR to exist — has this already been renamed?" >&2
  exit 1
fi

echo "==> 1/5  Moving package directory"
git mv "$OLD_PKG_DIR" "$NEW_PKG_DIR"

echo "==> 1/5  Flattening trutina/infrastructure/mongo/ -> trutina/storage_mongo/"
SRC_ROOT="$NEW_PKG_DIR/src/trutina"
mkdir -p "$SRC_ROOT/storage_mongo"
git mv "$SRC_ROOT"/infrastructure/mongo/* "$SRC_ROOT/storage_mongo/"
git rm -q "$SRC_ROOT/infrastructure/__init__.py"
rmdir "$SRC_ROOT/infrastructure"

echo "==> 2/5  Rewriting trutina.infrastructure.mongo -> trutina.storage_mongo (specific pattern)"
# Order matters: this MUST run before the bare-prefix pass below, or the
# bare pass would leave a dangling ".mongo" on every import.
grep -rlZ --include='*.py' --include='*.toml' --include='*.md' --include='*.yml' \
     --include='*.yaml' --include='*.html' -E 'trutina\.infrastructure\.mongo' . \
     2>/dev/null | xargs -0 -r sed -i -E 's/trutina\.infrastructure\.mongo/trutina.storage_mongo/g'

echo "==> 3/5  Rewriting bare trutina.infrastructure -> trutina.storage_mongo"
grep -rlZ --include='*.py' --include='*.toml' --include='*.md' --include='*.yml' \
     --include='*.yaml' --include='*.html' -E 'trutina\.infrastructure\b' . \
     2>/dev/null | xargs -0 -r sed -i -E 's/trutina\.infrastructure\b/trutina.storage_mongo/g'

echo "==> 4/5  Rewriting trutina-infrastructure -> trutina-storage-mongo (distribution name)"
grep -rlZ --include='*.py' --include='*.toml' --include='*.md' --include='*.yml' \
     --include='*.yaml' --include='*.html' -F 'trutina-infrastructure' . \
     2>/dev/null | xargs -0 -r sed -i 's/trutina-infrastructure/trutina-storage-mongo/g'

echo "==> 5/5  Patching conftest.py's _LAYER_DIRS entry"
if [ -f conftest.py ] && grep -q '"infrastructure": "infra"' conftest.py; then
  sed -i 's/"infrastructure": "infra"/"storage_mongo": "infra"/' conftest.py
else
  echo "    WARNING: expected _LAYER_DIRS entry not found in conftest.py — check by hand." >&2
fi

echo
echo "==> Checking for anything left behind"
LEFTOVER=$(grep -rln --include='*.py' --include='*.toml' --include='*.md' --include='*.yml' \
  --include='*.yaml' -E 'trutina\.infrastructure|trutina-infrastructure' . 2>/dev/null || true)
if [ -n "$LEFTOVER" ]; then
  echo "    Found remaining references — review these by hand:"
  echo "$LEFTOVER" | sed 's/^/      /'
else
  echo "    None found."
fi

cat <<'EOF'

Done. Manual follow-ups this script does NOT cover:

  - conftest.py's docstring prose that explains _LAYER_DIRS using
    "infrastructure" as its worked example — read it and update the
    example, the code itself already points at "storage_mongo".
  - .github/workflows/ci.yml: the `infrastructure:` job key and its
    display name "QG4 - Infrastructure" are arbitrary identifiers, not
    trutina.* references, so they were left alone. Rename for clarity
    if you want, purely cosmetic.
  - Confirm packages/storage-mongo/README.md and CONTEXT.md still read
    naturally after the mechanical substitution — prose sentences that
    said "trutina-infrastructure is the only package that imports beanie
    or pymongo" now correctly say "trutina-storage-mongo", but skim them.

Verification, in order:

  uv sync --all-packages
  uv run ruff format
  uv run ruff check
  uv run ty check
  uv run lint-imports
  uv run pytest --collect-only -q
  git add -A && git diff --stat --cached

If lint-imports fails on the forbidden/layers contracts, check root
pyproject.toml's [[tool.importlinter.contracts]] blocks landed correctly —
they use plain "trutina.infrastructure" (no .mongo suffix) as a layer name,
which the bare-prefix pass (step 3) should have caught.
EOF