#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Builds the production (runtime-stage) API image. Build context is the
# repo root, not apps/api/ -- required because trutina-api resolves its
# workspace dependencies (trutina-core, trutina-storage-postgres,
# trutina-config, and their own workspace dependencies) as
# `workspace = true` path dependencies (see apps/api/pyproject.toml
# [tool.uv.sources]), which uv can only resolve against the full
# workspace, not a single package's subdirectory.
#
# Usage:
#   tools/docker-build.sh [tag]
#
# Called directly by developers and by tools/docker-smoke.sh. Kept as
# its own script (rather than inlined into docker-smoke.sh) so a future
# registry-push job can reuse the same build step without duplicating it.

TAG="${1:-trutina-api:local}"

docker build \
    -f apps/api/Dockerfile \
    --target runtime \
    -t "$TAG" \
    .

echo "Built ${TAG}"