# Trutina Architecture

## Purpose

This document describes the current structure of the Trutina **workspace** — a `uv`
monorepo of independent packages, not a single application. It covers only
cross-package facts: dependency direction, layer boundaries, and each
package/app's responsibility. For any package's internal layering, file-by-file
responsibilities, or extension points, see that package's own `README.md` and
`CONTEXT.md` — this document deliberately does not restate them. For the repo-map
diagram and one-paragraph package pointers, see root `README.md`.

## Workspace Layout

```text
apps/
├── cli/                 trutina-cli
│   └── src/trutina/cli/
│       ├── main.py
│       ├── composition/      # app.py, bootstrap.py, context.py, state.py
│       ├── features/{account,journal,posting}/
│       ├── shared/{boundary,errors,formatters,interaction,ui}/
│       └── shell/            # loop.py, dispatch.py, completion.py, keybindings.py, builtins.py
└── api/                 trutina-api
    └── src/trutina/api/
        ├── composition/      # container.py, bootstrap.py, app.py, dependencies.py
        ├── features/{system,account,journal,posting}/
        └── shared/           # response.py, errors/{catalog,handlers,schemas}.py

packages/
├── core/                trutina-core
│   └── src/trutina/core/{account,journal,posting}/
│       ├── dtos.py, repo.py, service.py
│       └── schemas/
├── storage-mongo/       trutina-storage-mongo
│   └── src/trutina/storage_mongo/
│       ├── {account,journal,posting}/   # document.py, repository.py
│       ├── shared/                       # MongoExecutor, TimestampedDocument
│       └── connection.py, error_translation.py
├── storage-postgres/    trutina-storage-postgres
│   └── src/trutina/storage_postgres/
│       ├── {account,journal,posting}/   # repository.py
│       ├── shared/                       # PostgresExecutor, connect()/disconnect()
│       ├── models.py
│       └── alembic.ini, alembic/
├── config/              trutina-config
│   └── src/trutina/config/   # base.py, mongo.py, postgres.py, api.py
└── shared/              trutina-shared
    └── src/trutina/shared/   # rule.py, util.py, errors/{codes,errors,translators}.py

tests/                   # root-level shared fixtures/factories/fakes only — no test cases
```

Package/app ownership: `apps/cli/pyproject.toml`, `apps/api/pyproject.toml`,
`packages/{core,storage-mongo,storage-postgres,config,shared}/pyproject.toml` each
declare that package's own dependencies independently; the root `pyproject.toml`
declares the workspace (`tool.uv.workspace.members = ["apps/*", "packages/*"]`) and the
import-linter contracts below.

## Confirmed Dependency Direction

Enforced by `[[tool.importlinter.contracts]]` in the root `pyproject.toml` — checked in
CI (`uv run lint-imports`), not just documented convention:

```text
trutina.cli | trutina.api
        │
        ▼
trutina.storage_mongo | trutina.storage_postgres
        │
        ▼
trutina.core
        │
        ▼
trutina.shared | trutina.config
```

- **`type = "layers"`**, root packages `["trutina"]`: the four-tier chain above. Both
  storage backends sit at the same layer position — the contract permits either, not
  just one.
- **`type = "forbidden"`** (two contracts): `trutina.core` may never import `beanie` or
  `pymongo`, and separately may never import `sqlalchemy` or `asyncpg`, anywhere, at
  all. Stronger than "core sits above storage in the layer chain" — it asserts core has
  zero awareness that either backend exists.
- **`type = "layers"`**, scoped inside core: `trutina.core.posting → trutina.core.journal
→ trutina.core.account`, one-directional.

Confirmed per-package dependency facts (from each package's own `pyproject.toml`,
cross-checked against its README/CONTEXT):

| Package                    | Depends on (workspace)                                       | Depends on (external)                      |
| -------------------------- | ------------------------------------------------------------ | ------------------------------------------ |
| `trutina-shared`           | _(none)_                                                     | `pydantic`                                 |
| `trutina-config`           | _(none)_                                                     | `pydantic`, `pydantic-settings`            |
| `trutina-core`             | `trutina-shared`                                             | `pydantic`                                 |
| `trutina-storage-mongo`    | `trutina-shared`, `trutina-core`, `trutina-config`           | `beanie`, `pymongo`                        |
| `trutina-storage-postgres` | `trutina-shared`, `trutina-core`, `trutina-config`           | `sqlalchemy`, `asyncpg`, `alembic`         |
| `trutina-cli`              | `trutina-core`, `trutina-storage-postgres`, `trutina-config` | `typer`, `rich`, `anyio`, `prompt-toolkit` |
| `trutina-api`              | `trutina-core`, `trutina-storage-postgres`, `trutina-config` | `fastapi[standard]`, `uvicorn[standard]`   |

Neither `trutina-cli` nor `trutina-api` declares a dependency on `trutina-storage-mongo`
today — both migrated to `trutina-storage-postgres`. `trutina-storage-mongo` remains a
workspace member implementing the same three repository contracts, with its own CI lane
(`_test-layer-mongo.yml`), but is not consumed by either presentation app. `trutina-cli`
and `trutina-api` never depend on each other. `trutina-core` never depends on
`trutina-config` (a fact each package's own docs states independently and consistently).

## Layer Responsibilities

### `trutina.shared` — lowest layer

Reusable validation rules (`clean_account_name`, `account_lookup_key`,
`is_valid_line_amounts`) and the stable error contract (`ErrorCode`, `AppError`,
`ValidationAppError`, `FieldViolation`). Carries **no presentation text** — every
adapter (CLI, API) owns its own message/hint catalog keyed by `ErrorCode`. See
`packages/shared/README.md` / `CONTEXT.md`.

### `trutina.config`

Typed settings loaded from environment variables and dotenv files
(`TRUTINA_`/`TRUTINA_TEST_` prefixes), including `MongoSettings`, `PostgresSettings`, and
`ApiSettings`. No I/O beyond dotenv reads; no awareness of what consumes the settings it
produces. See `packages/config/README.md` / `CONTEXT.md`.

### `trutina.core` — the accounting domain

Validated domain schemas (`Account`, `JournalEntry`, `JournalLine`,
`LedgerPosting`, `ChartOfAccounts`), DTOs/ViewModels, three complete end-to-end
services (`AccountService`, `JournalService`, `PostingService`), and the abstract
`AccountRepo`/`JournalRepo`/`PostingRepo` contracts. Storage- and
transport-agnostic by construction (see the forbidden-imports contracts above). See
`packages/core/README.md` / `CONTEXT.md` for the full API surface, service
maturity table, and internal `posting→journal→account` ordering rationale.

### `trutina.storage_mongo`

One of two packages permitted to implement the core repository contracts against a real
backend; the only one permitted to import `beanie`/`pymongo`. Implements the three core
repository contracts against MongoDB, plus `connect()`/`disconnect()`/
`MongoConnection` and `MongoExecutor` (routes every Beanie call through
`translate_mongo_errors()`). Contains no business rules. Not currently depended on by
`apps/cli` or `apps/api`. See `packages/storage-mongo/README.md` / `CONTEXT.md`.

### `trutina.storage_postgres`

The storage backend `apps/cli` and `apps/api` actually construct today. Implements the
three core repository contracts with SQLAlchemy async + `asyncpg`, plus a
`PostgresConnection`/`connect()`/`disconnect()` lifecycle, `PostgresExecutor` (storage
error translation), and its own Alembic migration history. Contains no business rules.
See `packages/storage-postgres/README.md` / `CONTEXT.md`.

### `trutina.cli`

A synchronous Typer/Click presentation layer bridging to the async domain via
exactly one `anyio.BlockingPortal` for the life of the process. Feature commands
(`account`, `journal`, `posting`) each follow `command.py → parser.py/prompt.py →
handler.py → formatter.py`; a single `error_boundary()` seam renders
`AppError`/`ValidationAppError`/`pydantic.ValidationError` as Rich panels. Also
hosts a persistent interactive shell (`cli/shell/`) reusing the same Typer app for
dispatch and help. `composition/context.py` is the only CLI module that imports
`trutina.storage_postgres` types. See `apps/cli/README.md` / `CONTEXT.md` for the full
layer diagram, async execution model, and extension points.

### `trutina.api`

An async FastAPI presentation layer. Each feature follows Router → Request Schema
→ Mapper → Input DTO → Handler → Service → ViewModel → Presenter → Response
Schema; `system` is a documented flat exception with no body/domain model.
Composition is eager: `Container` (a frozen dataclass of the three services) is
built once at lifespan startup against `trutina.storage_postgres`, not lazily per
request like the CLI's `CliContext`. A single `register_exception_handlers()` seam is
the API's equivalent of the CLI's `error_boundary()`. See `apps/api/README.md` /
`CONTEXT.md`.

## Boundary Rules That Apply Across the Whole Workspace

- The shared error layer (`trutina.shared.errors`) never carries presentation
  text — CLI and API each own an independent message/hint/status-code catalog
  keyed by `ErrorCode`.
- `AppError`/`ValidationAppError` are the only exception types permitted to cross
  any service boundary, in both the CLI and API.
- Repository adapters (`trutina.storage_mongo`, `trutina.storage_postgres`) never
  contain business rules; uniqueness checks, cross-aggregate validation, and posting
  derivation all live in `trutina.core` services.
- Domain models (`trutina.core`) never import from either storage package,
  `trutina.cli`, or `trutina.api`.
- Neither presentation app (`cli`, `api`) may import the other.

## Testing Architecture (workspace-level)

- `pytest.ini` (root) sets `testpaths = tests apps packages`, `asyncio_mode = auto`,
  and registers markers `unit`, `integration` (speed axis); `core`, `infra`, `cli`,
  `api`, `shared`, `config` (layer axis); `mongo`, `postgres` (backend axis, meaningful
  only for `infra`-layer tests).
- Root `conftest.py` registers the shared fixture plugins
  (`tests.fixtures.{account,posting,journal,mongo,postgres,settings,services,cli,api}`)
  and mechanically enforces the marker discipline: every test must declare exactly one
  speed marker by hand; the layer marker is derived automatically from the test file's
  path; an `infra`-layer test must additionally resolve to exactly one backend marker
  (also path-derived). Collection fails loudly (`pytest.UsageError`) on any mismatch.
- Root `tests/` holds only shared fixtures/factories/fakes — no test cases. Each
  package/app's own tests live beside its code (`packages/core/.../tests/`,
  `apps/cli/.../tests/`, etc.), per that package's own testing documentation.
- Run a single layer or backend: `pytest -m "unit and cli"`,
  `pytest -m "integration and infra and postgres"`, etc.

## Known Gaps at the Workspace Level

- `trutina-shared`'s `util.default_posting_date()` is documented as unused by any
  active workflow, but is imported and called from `apps/cli`'s journal parser —
  unresolved; not re-confirmed against live source in this pass. See
  `PROJECT_CONTEXT.md`.
- `api/shared/errors/handlers.py`'s `_fill()` uses `except KeyError, IndexError:`,
  invalid Python 3 syntax. `apps/api/CONTEXT.md` now confirms this against live source
  as a real defect (previously an unconfirmed flag) — still not fixed. See
  `PROJECT_CONTEXT.md`.
- Root `compose.yml`/`compose.dev.yml` provision only MongoDB, even though `apps/api`
  and `apps/cli` both depend on `trutina-storage-postgres` today. See
  `PROJECT_CONTEXT.md`.
