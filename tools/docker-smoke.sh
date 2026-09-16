#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# QG7 smoke test: builds the production API image, boots it against a
# real PostgreSQL on an isolated Docker network, applies the Alembic
# migration history, then polls GET /health until it responds or the
# retry budget is exhausted.
#
# The migration step runs as a one-off container from the *same* image
# just built, invoking alembic directly via the image's own venv --
# packages/storage-postgres/{alembic.ini,alembic/} are present in the
# image because the Dockerfile COPYs packages/ as a whole directory,
# not just installed package files. This avoids requiring uv/Python on
# the host or in CI's smoke job to run migrations, and doubles as proof
# the shipped image can apply its own schema.
#
# This is the exact logic CI's QG7 job runs -- run it locally before
# pushing a Dockerfile/compose change rather than waiting on CI to catch
# a broken image.
#
# Usage:
#   tools/docker-smoke.sh
#
# Cleanup (containers + network) always runs via the EXIT trap, whether
# the smoke test passes, fails, or is interrupted (Ctrl-C).

NETWORK="trutina-smoke-net"
POSTGRES_NAME="trutina-smoke-postgres"
API_NAME="trutina-smoke-api"
IMAGE_TAG="trutina-api:smoke"
RETRIES=15
RETRY_INTERVAL=2

PG_USER="postgres"
PG_PASSWORD="postgres"
PG_DB="trutina_smoke"
PG_URI="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@${POSTGRES_NAME}:5432/${PG_DB}"

cleanup() {
    echo "==> Cleaning up smoke test resources"
    docker rm -f "$API_NAME" "$POSTGRES_NAME" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Building image"
tools/docker-build.sh "$IMAGE_TAG"

echo "==> Creating isolated network"
docker network create "$NETWORK" >/dev/null

echo "==> Starting Postgres"
docker run -d --rm \
    --name "$POSTGRES_NAME" \
    --network "$NETWORK" \
    -e POSTGRES_USER="$PG_USER" \
    -e POSTGRES_PASSWORD="$PG_PASSWORD" \
    -e POSTGRES_DB="$PG_DB" \
    postgres:16 >/dev/null

echo "==> Waiting for Postgres to accept connections"
for i in $(seq 1 "$RETRIES"); do
    if docker exec "$POSTGRES_NAME" pg_isready -U "$PG_USER" >/dev/null 2>&1; then
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "ERROR: Postgres did not become healthy in time" >&2
        exit 1
    fi
    sleep "$RETRY_INTERVAL"
done

echo "==> Applying Alembic migrations"
docker run --rm \
    --network "$NETWORK" \
    -e TRUTINA_POSTGRES__URI="$PG_URI" \
    --entrypoint /app/.venv/bin/python \
    "$IMAGE_TAG" \
    -m alembic -c /app/packages/storage-postgres/alembic.ini upgrade head

echo "==> Starting API"
docker run -d --rm \
    --name "$API_NAME" \
    --network "$NETWORK" \
    -e TRUTINA_POSTGRES__URI="$PG_URI" \
    -p 8000:8000 \
    "$IMAGE_TAG" >/dev/null

echo "==> Waiting for API /health"
for i in $(seq 1 "$RETRIES"); do
    if curl -fsS "http://localhost:8000/health" >/dev/null 2>&1; then
        echo "API is healthy"
        exit 0
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "ERROR: API did not become healthy in time" >&2
        echo "==> API logs:" >&2
        docker logs "$API_NAME" >&2 || true
        exit 1
    fi
    sleep "$RETRY_INTERVAL"
done