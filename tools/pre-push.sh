#!/usr/bin/env bash
# Local pre-push gate: fast, no external services required. Mirrors CI's
# QG1 (static analysis) plus the unit suite. Never mutates files — if this
# fails, run `tools/fix.sh` and re-commit. Integration tests need
# PostgreSQL and run in CI's later lanes, not here.
set -euo pipefail

# Resolve the repo root via git itself rather than a relative cd from
# this script's own path. tools/ is flat under the repo root (one level
# up, not two) — a hardcoded "../.." here previously walked past the
# repo entirely and onto the drive root, causing ruff to recurse into
# $RECYCLE.BIN and unrelated sibling projects. git rev-parse is correct
# regardless of how deep tools/ ever ends up nested.
cd "$(git rev-parse --show-toplevel)"

echo "==> ruff format --check"
uv run ruff format --check . || { echo "Run tools/fix.sh, then retry." >&2; exit 1; }

echo "==> ruff check"
uv run ruff check . || { echo "Run tools/fix.sh, then retry." >&2; exit 1; }

echo "==> ty check"
uv run ty check

echo "==> import boundary contracts"
uv run lint-imports

echo "==> marker hygiene"
uv run pytest --collect-only -q

echo "==> lane coverage"
bash tools/ci/check-lane-coverage.sh

echo "==> fast unit tests"
uv run pytest -m unit

echo "All checks passed."