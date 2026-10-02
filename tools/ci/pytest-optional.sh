#!/usr/bin/env bash
# Runs `pytest -m "<marker-expr>" <extra args...>`.
#
# An empty selection (pytest exit code 5, "no tests collected") FAILS by
# default. A mistyped selector, a stripped marker, or a mislabeled test
# directory would otherwise select nothing and pass silently. A lane that
# is legitimately empty today (e.g. a package scaffolded before its first
# test) must say so explicitly by passing --allow-empty as the FIRST
# argument; that is then visible in review and can be removed later.
#
# Usage:
#   tools/ci/pytest-optional.sh "unit and core" --cov=trutina --cov-report=term-missing
#   tools/ci/pytest-optional.sh --allow-empty "integration and shared"
set -euo pipefail

allow_empty=0
if [ "${1:-}" = "--allow-empty" ]; then
    allow_empty=1
    shift
fi

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 [--allow-empty] <marker-expr> [pytest args...]" >&2
    exit 2
fi

marker_expr="$1"
shift

set +e
uv run pytest -m "$marker_expr" "$@"
code=$?
set -e

if [ "$code" -eq 5 ]; then
    if [ "$allow_empty" -eq 1 ]; then
        echo "No tests collected for marker expression '$marker_expr' (--allow-empty) — treating as pass."
        exit 0
    fi
    echo "ERROR: no tests collected for marker expression '$marker_expr'." >&2
    echo "Fix the selector, or pass --allow-empty if this lane is intentionally empty." >&2
    exit 5
fi

exit "$code"
