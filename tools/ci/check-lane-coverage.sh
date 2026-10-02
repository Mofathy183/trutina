#!/usr/bin/env bash
# Fails if any collected test is not selected by at least one CI lane.
#
# Method: negate the union of every lane selector and collect. pytest exits 5
# ("no tests collected") when nothing is left over, which is the passing
# outcome here. Any test that IS collected is an orphan: it carries markers
# that no CI job selects, so it would never run in CI.
#
# KEEP IN SYNC with the selectors used in .github/workflows/*.yml. When you
# add or change a lane there, change it here in the same PR. Layer markers
# are derived by the root conftest.py from the test's directory.
set -euo pipefail

lanes=(
    # QG2 foundation (no external services)
    "unit and (shared or config or observability or authentication)"
    "integration and (shared or config or observability or authentication)"
    # QG3 core
    "unit and core"
    "integration and core"
    # QG4 storage
    "unit and infra and mongo"
    "integration and infra and mongo"
    "unit and infra and postgres"
    "integration and infra and postgres"
    # QG5 apps
    "unit and cli"
    "integration and cli"
    "unit and api"
    "integration and api"
)

expr=""
for lane in "${lanes[@]}"; do
    expr+="${expr:+ and }not ($lane)"
done

set +e
uv run pytest --collect-only -q -m "$expr"
code=$?
set -e

if [ "$code" -eq 5 ]; then
    echo "OK: every collected test belongs to a CI lane."
    exit 0
fi

if [ "$code" -eq 0 ]; then
    echo "ERROR: the tests listed above are not selected by any CI lane." >&2
    echo "Add a lane (workflow + this script) or fix their markers." >&2
    exit 1
fi

echo "ERROR: collection failed (exit $code)." >&2
exit "$code"
