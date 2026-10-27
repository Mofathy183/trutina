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
│       ├── composition/      # app.py, bootstrap.py, context.py, state.py, actor.py
│       ├── features/{account,journal,posting,trial_balance}/
│       ├── shared/{boundary,errors,formatters,interaction,ui}/
│       └── shell/            # loop.py, dispatch.py, completion.py, keybindings.py, builtins.py
└── api/                 trutina-api
    └── src/trutina/api/
        ├── composition/      # container.py, bootstrap.py, app.py, dependencies.py
        ├── features/{system,account,journal,posting,trial_balance}/
        └── shared/           # response.py, actor.py, errors/{catalog,handlers,schemas}.py

packages/
├── core/                trutina-core
│   └── src/trutina/core/{account,journal,posting,trial_balance}/
│       ├── dtos.py, repo.py, service.py
│       └── schemas/
├── observability/       trutina-observability
│   └── src/trutina/observability/
│       ├── __init__.py, configure.py, correlation.py, processors.py, asgi.py
│       └── tests/
├── authentication/      trutina-authentication
│   └── src/trutina/authentication/
│       ├── __init__.py
│       ├── {identity,credentials,tokens,shared}/   # contracts grouped by role
│       ├── credentials/{passwords,users,login}/    # credentials grouped by concern
│       └── tests/
├── storage-postgres/    trutina-storage-postgres
│   └── src/trutina/storage_postgres/
│       ├── {account,journal,posting,trial_balance}/   # repository.py
│       ├── audit/                        # model.py (audit_events)
│       ├── identity/                     # model.py, repository.py (users)
│       ├── login_attempt/                # model.py, repository.py (login_attempts)
│       ├── shared/                       # PostgresExecutor, connect()/disconnect()
│       ├── models.py
│       └── alembic.ini, alembic/
├── config/              trutina-config
│   └── src/trutina/config/   # base.py, postgres.py, api.py, logging.py
└── shared/              trutina-shared
    └── src/trutina/shared/   # rule.py, secret.py, util.py, errors/{codes,errors,translators}.py

tests/                   # root-level shared fixtures/factories/fakes only — no test cases
```

Package/app ownership: `apps/cli/pyproject.toml`, `apps/api/pyproject.toml`,
`packages/{core,storage-postgres,config,shared,observability,authentication}/pyproject.toml`
each declare that package's own dependencies independently; the root
`pyproject.toml` declares the workspace
(`tool.uv.workspace.members = ["apps/*", "packages/*"]`) and the import-linter
contracts below.

## Confirmed Dependency Direction

Enforced by `[[tool.importlinter.contracts]]` in the root `pyproject.toml` — checked in
CI (`uv run lint-imports`), not just documented convention:

```text
trutina.cli | trutina.api
        │
        ▼
trutina.storage_postgres | trutina.observability
        │
        ▼
trutina.core | trutina.authentication
        │
        ▼
trutina.shared | trutina.config
```

- **`type = "layers"`**, root packages `["trutina"]`: the four-tier chain above.
  `trutina.storage_postgres` and `trutina.observability` sit at the same layer
  position.
- **`type = "forbidden"`** (storage-specific): `trutina.core` may never import
  `sqlalchemy` or `asyncpg`, anywhere, at all. Stronger than "core sits above
  storage in the layer chain" — it asserts core has zero awareness that the
  storage backend exists.
- **`type = "forbidden"` ("Emitters use stdlib logging only")**: `trutina.core`,
  `trutina.shared`, `trutina.config`, `trutina.authentication`, and
  `trutina.storage_postgres` may never import `structlog` or
  `trutina.observability`. Every emitter outside the two presentation apps uses
  the standard library's `logging` module exclusively.
- **`type = "forbidden"` ("Observability stays generic")**: `trutina.observability`
  may never import `trutina.core`, the storage package, `fastapi`,
  `starlette`, `typer`, or `rich`. It has no domain vocabulary and no
  presentation-framework awareness — the mirror image of the previous contract.
- **`type = "layers"`**, scoped inside core: `trutina.core.posting → trutina.core.journal
→ trutina.core.account`, one-directional.
- `trutina.core.trial_balance` imports only from `trutina.shared`. It does not import
  `posting`, `journal`, or `account`, and no import-linter contract names it, so
  nothing mechanically prevents a future import from either direction. This is
  recorded here rather than described as enforced.
- `trutina.core` and `trutina.authentication` are independent siblings in the
  `layers` contract: neither may import the other. A separate `forbidden`
  contract states core has zero authentication awareness, and another keeps
  `trutina.authentication` free of `sqlalchemy`, `asyncpg`, `fastapi`,
  `starlette`, `typer` and `rich`.

Confirmed per-package dependency facts (from each package's own `pyproject.toml`,
cross-checked against its README/CONTEXT):

| Package                    | Depends on (workspace)                                                                | Depends on (external)                      |
| -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------ |
| `trutina-shared`           | _(none)_                                                                              | `pydantic`                                 |
| `trutina-config`           | _(none)_                                                                              | `pydantic`, `pydantic-settings`            |
| `trutina-core`             | `trutina-shared`                                                                      | `pydantic`                                 |
| `trutina-observability`    | `trutina-config`                                                                      | `structlog`, `platformdirs`                |
| `trutina-authentication`   | `trutina-shared`                                                                      | `pydantic`, `argon2-cffi`                  |
| `trutina-storage-postgres` | `trutina-shared`, `trutina-core`, `trutina-config`, `trutina-authentication`          | `sqlalchemy`, `asyncpg`, `alembic`         |
| `trutina-cli`              | `trutina-core`, `trutina-storage-postgres`, `trutina-config`, `trutina-observability` | `typer`, `rich`, `anyio`, `prompt-toolkit` |
| `trutina-api`              | `trutina-core`, `trutina-storage-postgres`, `trutina-config`, `trutina-observability` | `fastapi[standard]`, `uvicorn[standard]`   |

`trutina-cli` and `trutina-api` never depend on each other. `trutina-core` never depends on
`trutina-config`. Only `trutina-cli` and `trutina-api` depend on
`trutina-observability` — every other workspace package emits through the
standard library alone.
`trutina-authentication` is contracts, models and fakes; only `trutina-storage-postgres`
depends on it (for `UserRepo`), and `trutina-core` never will.

## Layer Responsibilities

### `trutina.shared` — lowest layer

Reusable validation rules (`clean_account_name`, `account_lookup_key`,
`is_valid_line_amounts`) and the stable error contract (`ErrorCode`, `AppError`,
`ValidationAppError`, `FieldViolation`). Carries **no presentation text** — every
adapter (CLI, API) owns its own message/hint catalog keyed by `ErrorCode`. See
`packages/shared/README.md` / `CONTEXT.md`.

### `trutina.config`

Typed settings loaded from environment variables and dotenv files
(`TRUTINA_`/`TRUTINA_TEST_` prefixes), including `PostgresSettings`,
`ApiSettings`, `LoggingSettings` and `AuthSettings`. No I/O beyond dotenv reads; no awareness of
what consumes the settings it produces — `LoggingSettings` describes shape only
and performs no logging setup of its own. See `packages/config/README.md` /
`CONTEXT.md`.

### `trutina.core` — the accounting domain

Validated domain schemas (`Account`, `JournalEntry`, `JournalLine`,
`LedgerPosting`, `ChartOfAccounts`, `AccountBalanceEntry`), DTOs/ViewModels, four
services (`AccountService`, `JournalService`, `PostingService`,
`TrialBalanceService`), and the abstract `AccountRepo`/`JournalRepo`/`PostingRepo`
contracts plus the read-only `TrialBalanceRepo`. `trial_balance` is a read model: it
aggregates already-posted ledger data and writes nothing. Storage- and
transport-agnostic by construction (see the forbidden-imports contracts above,
which also cover `structlog`/`trutina.observability`). Each service logs one
success event through the standard library's `logging` module after a
state-changing write actually persists, and never on a read or a raised
`AppError`/`ValidationAppError`. See `packages/core/README.md` / `CONTEXT.md` for
the full API surface, service maturity table, and internal
`posting→journal→account` ordering rationale.

### `trutina.observability`

The single place a process configures _where_ its logs go and _what they look
like_ — `configure_logging()`, `correlation_scope()`, `CorrelationIdMiddleware`.
Depends only on `trutina.config` (for `LoggingSettings`) and third-party
`structlog`/`platformdirs`. Never imports `trutina.core`, the storage package,
or any presentation framework — enforced by the "Observability stays generic"
contract. Consumed by exactly `trutina.cli` and `trutina.api`, each once at its
own composition root; every other package emits through plain
`logging.getLogger(__name__)` calls with zero dependency on this package. See
`packages/observability/README.md` / `CONTEXT.md`.

### `trutina.authentication`

Identity and authentication contracts: `Identity`, `AccessState`, a minimal `User`,
and abstract ports for password and refresh-token hashing, access-token issue and
verify, user, refresh-token and login-attempt stores, a clock, an event sink, a
per-write status checker, and the `Authenticator` use case. A peer of
`trutina.core`, never above or below it: core sees only an opaque `actor: str`
supplied by its caller. Contracts and models plus `Argon2PasswordHasher` and the service-only `RegistrationService`,
`PasswordAuthenticator` and `ThrottledAuthenticator`.
no token module, route or command exists, and no app depends on it.
The storage adapters, `PostgresUserRepo` and `PostgresLoginAttemptRepo`, live in `trutina.storage_postgres`.
The token and refresh-token contracts are provisional until the M3 ADR; `LoginAttemptRepo` was frozen in M2.4.
See `packages/authentication/README.md` / `CONTEXT.md`.

### `trutina.storage_postgres`

The storage backend `apps/cli` and `apps/api` construct, and the only package permitted
to import `sqlalchemy`/`asyncpg`. Implements the four core repository contracts with
SQLAlchemy async + `asyncpg`, plus a `PostgresConnection`/`connect()`/`disconnect()`
lifecycle, `PostgresExecutor` (storage error translation), and its own Alembic migration
history. `PostgresTrialBalanceRepo` runs one `GROUP BY` aggregation over the existing
`postings` table and adds no table or migration. Contains no business rules.
`connect()`/`disconnect()` each log one `db.connected`/`db.disconnected` line via stdlib
`logging` (never the connection URI), and the engine is constructed with
`hide_parameters=True` so a future exception's text never includes bound parameter
values. Alembic's `env.py` explicitly passes `disable_existing_loggers=False` to its
`fileConfig()` call, after a confirmed bug where the default value silently disabled
every non-Alembic-declared Python logger mid-process — see
`packages/storage-postgres/README.md` / `CONTEXT.md`.
`journal_entries` and `postings` carry a nullable `created_by` column recording the actor passed by the services;
it is not part of any domain model and is never returned by a repository read.
The account repository's write methods take `created_by` and record it as the actor of an append-only `audit_events` row,
written in the same transaction as the write.
It also implements `UserRepo` and `LoginAttemptRepo` (both defined in `trutina.authentication`)
against a `users` table and a `login_attempts` table.

### `trutina.cli`

A synchronous Typer/Click presentation layer bridging to the async domain via
exactly one `anyio.BlockingPortal` for the life of the process. Feature commands
(`account`, `journal`, `posting`) each follow `command.py → parser.py/prompt.py →
handler.py → formatter.py`; `trial-balance` is a flat top-level command with the same
layers minus `prompt.py`, since its one option is optional. A single `error_boundary()`
seam renders `AppError`/`ValidationAppError`/`pydantic.ValidationError` as Rich panels
and logs exactly one `command.failed` line per failure. Also hosts a persistent
interactive shell (`cli/shell/`) reusing the same Typer app for dispatch and help — each
dispatched shell line binds its own correlation id, never one id for the whole session.
`composition/context.py` is the only CLI module that imports `trutina.storage_postgres`
types. `main.py::main()` configures logging once, before the portal opens. See
`apps/cli/README.md` / `CONTEXT.md` for the full layer diagram, async execution model,
and extension points.

### `trutina.api`

An async FastAPI presentation layer. Each feature follows Router → Request Schema
→ Mapper → Input DTO → Handler → Service → ViewModel → Presenter → Response
Schema; `system` is a documented flat exception with no body/domain model, and
`trial_balance` (`GET /trial-balance`) has no Request Schema because it takes only an
optional `as_of` query parameter. Composition is eager: `Container` (a frozen dataclass
of the four services) is built once at lifespan startup against
`trutina.storage_postgres`, not lazily per request like the CLI's `CliContext`. A single
`register_exception_handlers()` seam is the API's equivalent of the CLI's
`error_boundary()`, and logs exactly one `request.failed` line per failure through a
shared `_log_failure()` helper. `create_app()` configures logging and attaches
`CorrelationIdMiddleware` before registering routers, so every request gets one
correlation id, echoed as `X-Request-ID` and present on every log line the request
produces. See `apps/api/README.md` / `CONTEXT.md`.

## Boundary Rules That Apply Across the Whole Workspace

- The shared error layer (`trutina.shared.errors`) never carries presentation
  text — CLI and API each own an independent message/hint/status-code catalog
  keyed by `ErrorCode`.
- `AppError`/`ValidationAppError` are the only exception types permitted to cross
  any service boundary, in both the CLI and API.
- The repository adapter (`trutina.storage_postgres`) never contains business
  rules; uniqueness checks, cross-aggregate validation, and posting derivation all
  live in `trutina.core` services.
- Domain models (`trutina.core`) never import from the storage package,
  `trutina.cli`, `trutina.api`, `trutina.observability`, `trutina.authentication`,
  or `structlog`.
- Neither presentation app (`cli`, `api`) may import the other.
- Every package outside `trutina.cli`/`trutina.api` emits through
  `logging.getLogger(__name__)` only. Only the two presentation apps decide how
  those records are formatted and where they're routed, and each does so exactly
  once, at its own composition root.
- A service or repository logs its own success; a raised `AppError`/
  `ValidationAppError` is logged exactly once, by the presentation-layer seam
  that catches it — never by both.

## Testing Architecture (workspace-level)

- `pytest.ini` (root) sets `testpaths = tests apps packages`, `asyncio_mode = auto`,
  and registers markers `unit`, `integration` (speed axis); `core`, `infra`, `cli`,
  `api`, `shared`, `config`, `observability`, `authentication` (layer axis); `postgres`
  (backend axis, meaningful only for `infra`-layer tests).
- Root `conftest.py` registers the shared fixture plugins
  (`tests.fixtures.{account,posting,journal,postgres,settings,services,cli,api,logging}`)
  and mechanically enforces the marker discipline: every test must declare exactly one
  speed marker by hand; the layer marker is derived automatically from the test file's
  path; an `infra`-layer test must additionally resolve to exactly one backend marker
  (also path-derived). Collection fails loudly (`pytest.UsageError`) on any mismatch.
- Root `tests/` holds only shared fixtures/factories/fakes — no test cases. Each
  package/app's own tests live beside its code (`packages/core/.../tests/`,
  `apps/cli/.../tests/`, etc.), per that package's own testing documentation.
- Run a single layer or backend: `pytest -m "unit and cli"`,
  `pytest -m "integration and infra and postgres"`, etc.
- `tests/fixtures/logging.py`'s autouse fixture removes only the handler
  `trutina-observability`'s `configure_logging()` installed itself, after every
  test, so pytest's own `caplog` handler is never disturbed.

## Known Gaps at the Workspace Level

- `trutina-shared`'s `util.default_posting_date()` is documented as unused by any
  active workflow, but is imported and called from `apps/cli`'s journal parser —
  unresolved; not re-confirmed against live source in this pass. See
  `PROJECT_CONTEXT.md`.
- The trial balance covers only accounts with postings and only PostgreSQL.
- Alembic's `fileConfig()` call for `trutina-storage-postgres` migrations now
  explicitly passes `disable_existing_loggers=False`, closing a confirmed bug
  where the default behavior silently disabled every non-Alembic-declared Python
  logger for the rest of a process — see `packages/storage-postgres/CONTEXT.md`
  for the full account, including the belt-and-braces re-enable step in
  `tests/fixtures/postgres.py`'s `schema_init`.
- `trutina-authentication` has contracts, test fakes, one concrete `Argon2PasswordHasher` and the service-only `RegistrationService`.
  No token module, route or command exists,
  and no app depends on it; only the `UserRepo` and `LoginAttemptRepo` adapters exist
  (only `ThrottledAuthenticator` writes login attempts, and nothing wires it)
  Token-related contracts are provisional until the M3 ADR.
