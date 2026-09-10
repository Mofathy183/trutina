# Trutina Architecture

## Purpose

This document describes the current structure of the Trutina **workspace** — a `uv`
monorepo of independent packages, not a single application. It covers only
cross-package facts: dependency direction, layer boundaries, and each
package/app's responsibility. For any package's internal layering, file-by-file
responsibilities, or extension points, see that package's own `README.md` and
`CONTEXT.md` — this document deliberately does not restate them.

## Workspace Layout

```text
apps/
├── cli/            trutina-cli
│   └── src/trutina/cli/
│       ├── main.py
│       ├── composition/      # app.py, bootstrap.py, context.py, state.py
│       ├── features/{account,journal,posting}/
│       ├── shared/{boundary,errors,formatters,interaction,ui}/
│       └── shell/            # loop.py, dispatch.py, completion.py, keybindings.py, builtins.py
└── api/            trutina-api
    └── src/trutina/api/
        ├── composition/      # container.py, bootstrap.py, app.py, dependencies.py
        ├── features/{system,account,journal,posting}/
        └── shared/           # response.py, errors/{catalog,handlers,schemas}.py

packages/
├── core/           trutina-core
│   └── src/trutina/core/{account,journal,posting}/
│       ├── dtos.py, repo.py, service.py
│       └── schemas/
├── infrastructure/ trutina-storage-mongo
│   └── src/trutina/infrastructure/mongo/
│       ├── {account,journal,posting}/   # document.py, repository.py
│       ├── shared/                       # MongoExecutor, TimestampedDocument
│       └── connection.py, error_translation.py
├── config/         trutina-config
│   └── src/trutina/config/   # base.py, mongo.py, api.py
└── shared/         trutina-shared
    └── src/trutina/shared/   # rule.py, util.py, errors/{codes,errors,translators}.py

tests/              # root-level shared fixtures/factories/fakes only — no test cases
```

Package/app ownership: `apps/cli/pyproject.toml`, `apps/api/pyproject.toml`,
`packages/{core,infrastructure,config,shared}/pyproject.toml` each declare that
package's own dependencies independently; the root `pyproject.toml` declares the
workspace (`tool.uv.workspace.members = ["apps/*", "packages/*"]`) and the
import-linter contracts below.

## Confirmed Dependency Direction

Enforced by `[[tool.importlinter.contracts]]` in the root `pyproject.toml` — these
are checked in CI (`uv run lint-imports`), not just documented convention:

```text
trutina.cli | trutina.api
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

- **`type = "layers"`**, root packages `["trutina"]`: the four-tier chain above.
- **`type = "forbidden"`**: `trutina.core` may never import `beanie` or `pymongo`,
  anywhere, at all — stronger than "core sits above infrastructure in the layer
  chain," it asserts core has zero awareness Mongo exists.
- **`type = "layers"`**, scoped inside core: `trutina.core.posting → trutina.core.journal → trutina.core.account`,
  one-directional. `posting` may import `journal`/`account`; `journal` may import
  `account`; `account` may import neither.

Confirmed per-package dependency facts (from each package's own `pyproject.toml`,
cross-checked against its README/CONTEXT):

| Package                  | Depends on (workspace)                                     | Depends on (external)                      |
| ------------------------ | ---------------------------------------------------------- | ------------------------------------------ |
| `trutina-shared`         | _(none)_                                                   | `pydantic`                                 |
| `trutina-config`         | _(none)_                                                   | `pydantic`, `pydantic-settings`            |
| `trutina-core`           | `trutina-shared`                                           | `pydantic`                                 |
| `trutina-storage-mongo` | `trutina-shared`, `trutina-core`, `trutina-config`         | `beanie`, `pymongo`                        |
| `trutina-cli`            | `trutina-core`, `trutina-storage-mongo`, `trutina-config` | `typer`, `rich`, `anyio`, `prompt-toolkit` |
| `trutina-api`            | `trutina-core`, `trutina-storage-mongo`, `trutina-config` | `fastapi[standard]`, `uvicorn[standard]`   |

`trutina-cli` and `trutina-api` never depend on each other. `trutina-core` never
depends on `trutina-config` (a fact each package's own docs states independently
and consistently).

## Layer Responsibilities

### `trutina.shared` — lowest layer

Reusable validation rules (`clean_account_name`, `account_lookup_key`,
`is_valid_line_amounts`) and the stable error contract (`ErrorCode`, `AppError`,
`ValidationAppError`, `FieldViolation`). Carries **no presentation text** — every
adapter (CLI, API) owns its own message/hint catalog keyed by `ErrorCode`. See
`packages/shared/README.md` / `CONTEXT.md`.

### `trutina.config`

Typed settings loaded from environment variables and dotenv files
(`TRUTINA_`/`TRUTINA_TEST_` prefixes). No I/O beyond dotenv reads; no awareness of
what consumes the settings it produces. See `packages/config/README.md` / `CONTEXT.md`.

### `trutina.core` — the accounting domain

Validated domain schemas (`Account`, `JournalEntry`, `JournalLine`,
`LedgerPosting`, `ChartOfAccounts`), DTOs/ViewModels, three complete end-to-end
services (`AccountService`, `JournalService`, `PostingService`), and the abstract
`AccountRepo`/`JournalRepo`/`PostingRepo` contracts. Storage- and
transport-agnostic by construction (see the forbidden-imports contract above). See
`packages/core/README.md` / `CONTEXT.md` for the full API surface, service
maturity table, and internal `posting→journal→account` ordering rationale.

### `trutina.storage_mongo`

The only package permitted to import `beanie`/`pymongo`. Implements the three core
repository contracts against MongoDB, plus `connect()`/`disconnect()`/
`MongoConnection` and `MongoExecutor` (routes every Beanie call through
`translate_mongo_errors()`). Contains no business rules. See
`packages/infrastructure/README.md` / `CONTEXT.md`.

### `trutina.cli`

A synchronous Typer/Click presentation layer bridging to the async domain via
exactly one `anyio.BlockingPortal` for the life of the process. Feature commands
(`account`, `journal`, `posting`) each follow `command.py → parser.py/prompt.py →
handler.py → formatter.py`; a single `error_boundary()` seam renders
`AppError`/`ValidationAppError`/`pydantic.ValidationError` as Rich panels. Also
hosts a persistent interactive shell (`cli/shell/`) reusing the same Typer app for
dispatch and help. See `apps/cli/README.md` / `CONTEXT.md` for the full layer
diagram, async execution model, and extension points.

### `trutina.api`

An async FastAPI presentation layer. Each feature follows Router → Request Schema
→ Mapper → Input DTO → Handler → Service → ViewModel → Presenter → Response
Schema; `system` is a documented flat exception with no body/domain model.
Composition is eager: `Container` (a frozen dataclass of the three services) is
built once at lifespan startup, not lazily per request like the CLI's
`CliContext`. A single `register_exception_handlers()` seam is the API's
equivalent of the CLI's `error_boundary()`. See `apps/api/CONTEXT.md` (no
`apps/api/README.md` exists yet — flagged in `PROJECT_CONTEXT.md`).

## Boundary Rules That Apply Across the Whole Workspace

- The shared error layer (`trutina.shared.errors`) never carries presentation
  text — CLI and API each own an independent message/hint/status-code catalog
  keyed by `ErrorCode`.
- `AppError`/`ValidationAppError` are the only exception types permitted to cross
  any service boundary, in both the CLI and API.
- Repository adapters (`trutina.storage_mongo`) never contain business rules;
  uniqueness checks, cross-aggregate validation, and posting derivation all live
  in `trutina.core` services.
- Domain models (`trutina.core`) never import from `trutina.storage_mongo`,
  `trutina.cli`, or `trutina.api`.
- Neither presentation app (`cli`, `api`) may import the other.

## Testing Architecture (workspace-level)

- `pytest.ini` (root) sets `testpaths = tests apps packages`, `asyncio_mode = auto`,
  and registers markers `unit`, `integration` (speed axis) plus `core`, `infra`,
  `cli`, `api`, `shared` (layer axis).
- Root `conftest.py` registers the shared fixture plugins
  (`tests.fixtures.{account,posting,journal,mongo,settings,services,cli,api}`) and
  mechanically enforces the two-axis marker discipline: every test must declare
  exactly one speed marker by hand; the layer marker is derived automatically from
  the test file's path and collection fails loudly if a test declares a
  conflicting layer marker itself.
- Root `tests/` holds only shared fixtures/factories/fakes — no test cases. Each
  package/app's own tests live beside its code (`packages/core/.../tests/`,
  `apps/cli/.../tests/`, etc.), per that package's own testing documentation.
- Run a single layer: `pytest -m "unit and cli"`, `pytest -m "integration and infra"`, etc.

## Known Gaps at the Workspace Level

- `apps/api` has no `README.md` — its documented facts here come from
  `CONTEXT.md` only.
- `trutina-shared`'s `util.default_posting_date()` is documented as unused by any
  active workflow, but is imported and called from `apps/cli`'s journal parser —
  see `PROJECT_CONTEXT.md` for this unresolved cross-package conflict.
- `apps/api/CONTEXT.md` flags a possible invalid Python syntax
  (`except KeyError, IndexError:`) in `api/shared/errors/handlers.py`, unconfirmed
  against the live file at the time of that pass.
