# Trutina

Trutina is a Python double-entry bookkeeping engine, built as a `uv` workspace: one
shared accounting-domain package, one storage adapter package, one settings package,
and two thin presentation apps (a Typer/Rich CLI and a FastAPI HTTP API) that both
sit on top of the same domain code.

## What's Actually Here

- **`packages/core`** (`trutina-core`) — the accounting domain: validated models,
  `AccountService`/`JournalService`/`PostingService`, and the abstract
  `AccountRepo`/`JournalRepo`/`PostingRepo` contracts. Zero knowledge of storage,
  HTTP, or terminals. See `packages/core/README.md` / `CONTEXT.md`.
- **`packages/infrastructure`** (`trutina-storage-mongo`) — concrete MongoDB/Beanie
  implementations of the three repository contracts, plus connection lifecycle and
  error-translation helpers. See `packages/infrastructure/README.md` / `CONTEXT.md`.
- **`packages/config`** (`trutina-config`) — typed, environment-driven settings
  (`Settings`, `TestSettings`, `MongoSettings`, `ApiSettings`). Depends on nothing
  else in the workspace. See `packages/config/README.md` / `CONTEXT.md`.
- **`packages/shared`** (`trutina-shared`) — the lowest-level package: reusable
  validation rules and the shared `ErrorCode`/`AppError`/`ValidationAppError` model.
  Depends on nothing but `pydantic`. See `packages/shared/README.md` / `CONTEXT.md`.
- **`apps/cli`** (`trutina-cli`) — a Typer/Rich terminal application, plus a
  persistent interactive shell with Claude Code–style slash-command completion. See
  `apps/cli/README.md` / `CONTEXT.md`.
- **`apps/api`** (`trutina-api`) — a FastAPI HTTP presentation layer over the same
  domain services, following a fixed Router → Mapper → Handler → Presenter pipeline
  per feature. See `apps/api/CONTEXT.md` (no `apps/api/README.md` exists yet).

Each package/app's own README/CONTEXT is the authoritative reference for its
internals. This file and `ARCHITECTURE.md`/`PROJECT_CONTEXT.md`/`AGENTS.md` describe
only cross-cutting, workspace-level facts — they never restate a package's own
internal detail.

## Repository Structure

```text
.
├── apps/
│   ├── cli/                  # trutina-cli
│   │   └── src/trutina/cli/
│   │       ├── main.py                # console entry point, single BlockingPortal
│   │       ├── composition/           # app.py, bootstrap.py, context.py, state.py
│   │       ├── features/{account,journal,posting}/
│   │       │   └── command.py, parser.py, prompt.py, handler.py, formatter.py, tests/
│   │       ├── shared/
│   │       │   ├── boundary/          # error_boundary.py
│   │       │   ├── errors/            # CLI-owned message/hint catalogs
│   │       │   ├── formatters/        # AppError/ValidationError -> Rich panels
│   │       │   ├── interaction/       # ask/select/confirm prompt primitives
│   │       │   └── ui/                # console, widgets, theme/, shell_banner.py, logo.py
│   │       └── shell/                 # interactive REPL: loop, dispatch, completion,
│   │                                   # keybindings, builtins
│   └── api/                  # trutina-api
│       └── src/trutina/api/
│           ├── composition/           # container.py, bootstrap.py, app.py, dependencies.py
│           ├── features/{system,account,journal,posting}/
│           │   └── router.py, schemas.py, mapper.py, handler.py, presenter.py, tests/
│           └── shared/                # response.py, errors/{catalog,handlers,schemas}.py
├── packages/
│   ├── core/                 # trutina-core
│   │   └── src/trutina/core/{account,journal,posting}/
│   │       └── dtos.py, repo.py, service.py, schemas/, tests/
│   ├── infrastructure/       # trutina-storage-mongo
│   │   └── src/trutina/infrastructure/mongo/
│   │       ├── {account,journal,posting}/  # document.py, repository.py, tests/
│   │       ├── shared/                     # document.py, repository.py (MongoExecutor)
│   │       └── connection.py, error_translation.py
│   ├── config/                # trutina-config
│   │   └── src/trutina/config/  # base.py (Settings/TestSettings), mongo.py, api.py
│   └── shared/                 # trutina-shared
│       └── src/trutina/shared/  # rule.py, util.py, errors/{codes,errors,translators}.py
├── tests/                     # root-level shared fixtures/factories/fakes only
│   ├── fixtures/  ├── factories/  └── fakes/
├── conftest.py                 # fixture-plugin registration + marker enforcement hook
├── pytest.ini
├── ty.toml
├── ruff.toml
├── pyproject.toml              # workspace root, import-linter contracts
└── compose.yml                 # mongo + api services for local/dev
```

## Confirmed Dependency Direction

```text
apps.cli | apps.api
        │
        ▼
trutina.storage_mongo
        │
        ▼
trutina.core
        │
        ▼
trutina.shared | trutina.config
```

Enforced mechanically by import-linter contracts in the root `pyproject.toml`:

- Layered: `trutina.cli | trutina.api → trutina.storage_mongo → trutina.core → trutina.shared | trutina.config`.
- Forbidden: `trutina.core` must never import `beanie` or `pymongo`.
- Internal to core: `trutina.core.posting → trutina.core.journal → trutina.core.account` (one-directional).

`trutina-config` and `trutina-shared` each depend on nothing else in the workspace.
`apps/cli` never depends on `apps/api` and vice versa.

## Technology Stack

- Python 3.14+, managed as a `uv` workspace (`tool.uv.workspace.members = ["apps/*", "packages/*"]`).
- Pydantic v2 — domain and DTO validation everywhere.
- Typer + Rich + AnyIO + prompt-toolkit — the CLI and its interactive shell.
- FastAPI + Uvicorn — the HTTP API.
- Beanie + PyMongo (async) — MongoDB persistence, isolated to `trutina-storage-mongo`.
- Pytest (`asyncio_mode = auto`), Ruff, `ty`, `import-linter` — testing and static checks.

## Development Setup

```bash
uv sync --all-packages
```

```bash
uv run pytest -m unit
uv run pytest -m integration      # requires MongoDB; see compose.yml / .env.test.example
```

```bash
uv run ruff check
uv run ruff format
uv run ty check
uv run lint-imports                # enforces the import-linter contracts above
```

Convenience scripts: `tools/bootstrap.sh` (sync everything), `tools/fix.sh` (auto-fix
formatting/lint), `tools/pre-push.sh` (the fast local gate CI also runs first),
`tools/docker-build.sh` / `tools/docker-smoke.sh` (build and smoke-test the API image).

## Environment Configuration

```bash
cp .env.example .env
cp .env.test.example .env.test
```

Production reads `TRUTINA_`-prefixed variables; tests read `TRUTINA_TEST_`-prefixed
variables from a separate database. Nested settings use a double underscore
(`TRUTINA_MONGO__URI`). See `packages/config/README.md` for the full field list.

## Current Status

| Area                                                           | Status                                                                                                                          |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Account domain, service, Mongo repository                      | Implemented, tested end-to-end                                                                                                  |
| Journal domain, service, Mongo repository                      | Implemented, tested end-to-end                                                                                                  |
| Posting domain, service, Mongo repository                      | Implemented, tested end-to-end                                                                                                  |
| CLI: `account`/`journal`/`posting` command groups              | Implemented, unit + integration tested                                                                                          |
| CLI: interactive shell (slash completion, help shorthands)     | Implemented, unit tested                                                                                                        |
| API: `account`/`journal`/`posting` feature routers             | Present per `apps/api/CONTEXT.md`'s fixed pipeline; no `apps/api/README.md` to confirm full test-tier coverage — see Known Gaps |
| API: `system` (health/root)                                    | Implemented as a documented flat exception                                                                                      |
| Trial balance / reporting                                      | Not implemented                                                                                                                 |
| Import/export, external integrations                           | Not implemented                                                                                                                 |
| `modules/journal/rule.py`, `modules/posting/rule.py` scaffolds | Unconfirmed in this pass — not re-verified against `trutina-core`'s current README/CONTEXT                                      |

See `ROADMAP.md` for what's next and `PROJECT_CONTEXT.md` for the reasoning behind
the current shape.

## Known Gaps / Open Flags

- `apps/api/README.md` does not exist yet; API-layer facts above are drawn solely
  from `apps/api/CONTEXT.md`.
- `trutina-shared` documents `util.default_posting_date()` as unused by any active
  workflow, but `apps/cli`'s journal parser (`cli/features/journal/parser.py`)
  visibly imports and calls it. Flagged, not resolved, in `PROJECT_CONTEXT.md`.
- `MongoPostingRepo.save_many()` has no multi-document transaction — a mid-batch
  failure can partially persist a journal's postings (accepted, documented risk).
- `get_field_violations()` (in `trutina-shared`) downgrades domain-raised
  `ErrorCode`s to `UNKNOWN_ERROR` on `FieldViolation.code`; both the CLI and API
  layers work around this by recovering the real code from `FieldViolation.value`.

## Contributing

Keep changes scoped to the package/app they belong to. Update that package's own
README/CONTEXT when its structure or maturity changes — do not let root docs drift
into re-describing package internals. Run `tools/pre-push.sh` before pushing.

## License

No license file is present in the repository yet.
