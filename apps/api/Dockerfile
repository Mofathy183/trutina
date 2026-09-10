# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT, not apps/api/ — build with:
#   docker build -f apps/api/Dockerfile -t trutina-api .
#
# This is required because trutina-api depends on trutina-core,
# trutina-storage-mongo, and trutina-config as `workspace = true`
# path dependencies (see apps/api/pyproject.toml [tool.uv.sources]).
# uv can only resolve those against the full workspace, not a
# single package's subdirectory.

# ---------------------------------------------------------------------------
# Stage: builder
#   Resolves the workspace + syncs only the trutina-api dependency subset.
#   Split into two RUN steps so dependency-only changes (pyproject.toml,
#   uv.lock) cache separately from source-only changes.
#
#   IMPORTANT: WORKDIR is /app here (not /workspace) so that the venv's
#   baked-in absolute shebang paths (e.g. #!/app/.venv/bin/python) remain
#   valid once /app/.venv is copied into the runtime stage below. If this
#   path ever changes, it must change in both stages together, AND in
#   compose.dev.yml's volume/watch paths, which currently assume /app.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# --- Manifests only: cache dependency resolution across source edits ---
COPY pyproject.toml uv.lock ./
COPY packages/shared/pyproject.toml packages/shared/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/config/pyproject.toml packages/config/pyproject.toml
COPY packages/storage-mongo/pyproject.toml packages/storage-mongo/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package trutina-api --no-install-workspace

# --- Real source: finish the sync now that workspace members are present ---
COPY packages/ packages/
COPY apps/api/ apps/api/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package trutina-api

# ---------------------------------------------------------------------------
# Stage: runtime  (production image — this is what compose.yml/CI build)
#   Slim, non-root, no build toolchain, no dev dependencies.
#
#   WORKDIR matches builder's /app exactly — see note above.
#
#   `packages/` MUST be copied here, not just `apps/api/`. Workspace
#   members are installed EDITABLE (uv's default for workspace deps), so
#   the venv only contains .pth files pointing back at each package's
#   `src/` directory — the actual code never lands in site-packages.
#   Without this line, every `trutina.{core,config,storage-mongo,shared}`
#   import fails at runtime with ModuleNotFoundError even though
#   `uv pip list` shows the package "installed".
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/apps/api /app/apps/api

ENV PATH="/app/.venv/bin:$PATH"
USER appuser

EXPOSE 8000

# Assumes the `system` feature's GET /health endpoint (see PROJECT_CONTEXT.md).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# trutina.api.main is a console-script entry point (calls uvicorn.run()
# internally against trutina.api.composition.app:app) -- it does NOT
# expose a module-level `app` object itself. Target the real ASGI app
# module/attribute directly here instead, matching main.py's own
# uvicorn.run(...) call target.
CMD ["uvicorn", "trutina.api.composition.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Stage: dev  (local development only — used via compose.dev.yml)
#   Reuses `builder` (full workspace, dev deps, already-synced .venv)
#   instead of the slim runtime stage, and runs uvicorn with --reload.
#   Each workspace package that feeds the API needs its own --reload-dir,
#   since uvicorn's watcher does not recurse into arbitrary sibling paths
#   by default. `packages/shared` is included because trutina-core and
#   trutina-storage-mongo both depend on it — an edit there must also
#   trigger a reload.
# ---------------------------------------------------------------------------
FROM builder AS dev

WORKDIR /app

CMD ["uv", "run", "--package", "trutina-api", "uvicorn", \
        "trutina.api.composition.app:app", \
        "--host", "0.0.0.0", "--port", "8000", \
        "--reload", \
        "--reload-dir", "/app/apps/api/src", \
        "--reload-dir", "/app/packages/core/src", \
        "--reload-dir", "/app/packages/config/src", \
        "--reload-dir", "/app/packages/storage-mongo/src", \
        "--reload-dir", "/app/packages/shared/src"]