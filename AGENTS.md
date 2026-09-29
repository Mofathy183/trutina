# Trutina

Python double-entry bookkeeping engine. `uv` workspace: `apps/{cli,api}` +
`packages/{core,storage-mongo,storage-postgres,config,shared,observability}`.
Root docs cover cross-cutting facts only — package/app internals are
documented in that package's own README.md/CONTEXT.md.

## Tech Stack

- Python 3.14+, `uv` workspace (`tool.uv.workspace.members = ["apps/*", "packages/*"]`)
- Pydantic v2, Pydantic Settings
- Typer, Rich, AnyIO, prompt-toolkit (CLI)
- FastAPI, Uvicorn (API)
- SQLAlchemy 2.0 async, `asyncpg`, Alembic — isolated to `trutina-storage-postgres`
- Beanie, PyMongo (async) — isolated to `trutina-storage-mongo`
- structlog, platformdirs — isolated to `trutina-observability`
- Pytest (`asyncio_mode = auto`), Ruff, `ty`, `import-linter`

## Workspace Packages/Apps

| Package                    | Import path                | Depends on (workspace)                                                        | Depends on (external)                |
| -------------------------- | -------------------------- | ----------------------------------------------------------------------------- | ------------------------------------ |
| `trutina-shared`           | `trutina.shared`           | none                                                                          | pydantic                             |
| `trutina-config`           | `trutina.config`           | none                                                                          | pydantic, pydantic-settings          |
| `trutina-core`             | `trutina.core`             | trutina-shared                                                                | pydantic                             |
| `trutina-observability`    | `trutina.observability`    | trutina-config                                                                | structlog, platformdirs              |
| `trutina-storage-mongo`    | `trutina.storage_mongo`    | trutina-shared, trutina-core, trutina-config                                  | beanie, pymongo                      |
| `trutina-storage-postgres` | `trutina.storage_postgres` | trutina-shared, trutina-core, trutina-config                                  | sqlalchemy, asyncpg, alembic         |
| `trutina-cli`              | `trutina.cli`              | trutina-core, trutina-storage-postgres, trutina-config, trutina-observability | typer, rich, anyio, prompt-toolkit   |
| `trutina-api`              | `trutina.api`              | trutina-core, trutina-storage-postgres, trutina-config, trutina-observability | fastapi[standard], uvicorn[standard] |

`trutina-storage-mongo` is a workspace member with its own CI lane but is not
declared as a dependency of either `trutina-cli` or `trutina-api` today. `trutina-cli`
never depends on `trutina-api`, or vice versa. `trutina-core` never depends on
`trutina-config`. `trutina-core`, `trutina-shared`, `trutina-config`, and both
storage packages never depend on `trutina-observability` or `structlog` — only
`trutina-cli` and `trutina-api` do, each exactly once at their own composition
root.

## Import-Linter Contracts (root `pyproject.toml`, enforced in CI)

- `layers`: `trutina.cli | trutina.api → trutina.storage_mongo | trutina.storage_postgres | trutina.observability → trutina.core → trutina.shared | trutina.config`
- `forbidden`: `trutina.core` must never import `beanie` or `pymongo`
- `forbidden`: `trutina.core` must never import `sqlalchemy` or `asyncpg`
- `layers` (internal to core): `trutina.core.posting → trutina.core.journal → trutina.core.account`
- `forbidden` ("Emitters use stdlib logging only"): `trutina.core`, `trutina.shared`, `trutina.config`, `trutina.storage_mongo`, `trutina.storage_postgres` must never import `structlog` or `trutina.observability`
- `forbidden` ("Observability stays generic"): `trutina.observability` must never import `trutina.core`, either storage package, `fastapi`, `starlette`, `typer`, or `rich`

## Repository Layout (real, current)

```text
apps/cli/src/trutina/cli/
  main.py, composition/{app,bootstrap,context,state}.py,
  features/{account,journal,posting}/{command,parser,prompt,handler,formatter}.py,
  features/trial_balance/{command,parser,handler,formatter}.py   # flat command, no prompt.py
  shared/{boundary/error_boundary.py, errors/, formatters/, interaction/, ui/{theme/,shell_banner.py,logo.py}},
  shell/{loop,dispatch,completion,keybindings,builtins}.py

apps/api/src/trutina/api/
  composition/{container,bootstrap,app,dependencies}.py,
  features/{system,account,journal,posting,trial_balance}/{router,schemas,mapper,handler,presenter}.py,
  shared/{response.py, errors/{catalog,handlers,schemas}.py}

packages/core/src/trutina/core/{account,journal,posting}/{dtos,repo,service}.py, schemas/
packages/core/src/trutina/core/trial_balance/{dtos,repo,service}.py, schemas/account_balance.py
packages/observability/src/trutina/observability/
  __init__.py, configure.py, correlation.py, processors.py, asgi.py
packages/storage-mongo/src/trutina/storage_mongo/
  {account,journal,posting}/{document,repository}.py, shared/, connection.py, error_translation.py
packages/storage-postgres/src/trutina/storage_postgres/
  {account,journal,posting}/repository.py, shared/{connection.py, execution/}, models.py
packages/storage-postgres/src/trutina/storage_postgres/trial_balance/repository.py
packages/storage-postgres/alembic.ini, alembic/
packages/config/src/trutina/config/{base,mongo,postgres,api,logging}.py
packages/shared/src/trutina/shared/{rule,util}.py, errors/{codes,errors,translators}.py

tests/{fixtures,factories,fakes}/     # shared test infra only, no test cases
tests/fixtures/logging.py             # autouse reset of trutina-observability's installed handler
tests/fakes/trial_balance_repo.py, tests/factories/trial_balance.py
conftest.py, pytest.ini, ty.toml, ruff.toml, pyproject.toml, compose.yml
```

Package/app own tests live beside their own code (e.g.
`packages/core/src/trutina/core/account/tests/`, `apps/cli/.../features/account/tests/`).

## Confirmed Domain Rules (per `trutina-core`)

- Every journal entry must balance (total debits == total credits).
- A journal line carries exactly one side (debit XOR credit), never both, never
  neither; negative amounts are invalid.
- `JournalEntry` requires at least two lines and a positive `journal_number`.
- `JournalEntry.posting_date` / `LedgerPosting.posting_date` must be later than
  2020-01-01 and not in the future.
- `LedgerPosting` is frozen after creation.
- `Account.normal_balance` is derived from `AccountCategory`, never stored
  independently.
- `ChartOfAccounts` enforces unique codes and unique canonical names,
  case-insensitively (`account_lookup_key()` uses Unicode `casefold()`, not `lower()`).
- Account aliases and `ChartOfAccounts.resolve()` are **not implemented**.
- `AppError` (and its `ValidationAppError` subclass) is the only exception type
  permitted to cross a service boundary in either presentation app.
- A trial balance is derived from persisted `LedgerPosting` records only. An unposted
  `JournalEntry` never affects it.
- `AccountBalanceEntry` carries independent, non-negative `debit_total` and
  `credit_total` per account — never netted, never single-sided.
- `TrialBalanceViewModel.total_debits`, `total_credits`, and `is_balanced` are
  computed, never stored. An empty report is balanced.
- Only accounts with at least one posting in scope appear. Postings are grouped
  case-insensitively via `account_lookup_key()`.
- `as_of_date=None` means all time; otherwise only postings with
  `posting_date <= as_of_date` are included. The value is not validated.
- Each of the four core services (`AccountService`, `JournalService`,
  `PostingService`, `TrialBalanceService`) logs one INFO line on a successful
  state change (or, for trial balance, on report generation) and never on a
  read or a raised `AppError`. No monetary field is ever included in these
  log events.

## Error Model

- `trutina.shared.errors`: `ErrorCode`, `AppError`, `ValidationAppError`,
  `FieldViolation`, `pydantic_error()`, `get_field_violations()`, `PYDANTIC_CODES`.
- Known gap: `get_field_violations()` downgrades domain-raised `ErrorCode`s to
  `UNKNOWN_ERROR` on `FieldViolation.code`; the real code survives only in
  `FieldViolation.value`. Both `trutina-cli` and `trutina-api` recover it there.
- No presentation text lives in `trutina.shared` — CLI (`cli/shared/errors/`) and
  API (`api/shared/errors/catalog.py`) each own an independent message/hint/status
  catalog keyed by `ErrorCode`.
- Both presentation layers log exactly one line per caught failure, through a
  single shared helper each owns (`_log_failure()` in the CLI's
  `error_boundary()` and in the API's `shared/errors/handlers.py`). Which
  `ErrorCode`s count as an ERROR-level incident is decided independently per
  app (`_ERROR_LEVEL_CODES` in the CLI, the HTTP-status threshold in the API) —
  deliberately not shared, for the same reason CLI/API error wording isn't
  shared. See `trutina-observability`'s own CONTEXT.md for the full rationale.

## Logging and Correlation

- `trutina-observability` (`trutina.observability`) is the single place a
  process decides _where_ logs go and _what they look like_.
  `configure_logging(settings.logging, app=...)` is idempotent and called
  once per process — from `apps/api/composition/app.py::create_app()` (and
  redundantly, for the `--reload` parent-process case, from
  `apps/api/main.py::main()`), and from `apps/cli/main.py::main()`.
- Every other package (`trutina.core`, `trutina.shared`, `trutina.config`,
  both storage packages) emits through plain `logging.getLogger(__name__)`
  calls only, with zero import of `trutina.observability` or `structlog` —
  enforced by the "Emitters use stdlib logging only" import-linter contract.
- A correlation id is bound per HTTP request (`CorrelationIdMiddleware`,
  reused from a valid inbound `X-Request-ID` or generated) and per CLI
  command (`correlation_scope()`, once per one-shot invocation in
  `main.py::run()`, once per dispatched line in the interactive shell). A
  context variable bound on the CLI's main thread reaches code run through
  `anyio`'s `BlockingPortal.call(...)` without a re-bind.
- Lifecycle/transport events: `app.started`/`app.stopped`,
  `db.connected`/`db.disconnected` (both storage backends — never logs a
  connection URI, since either can embed credentials),
  `request.completed`/`request.failed` (API), `command.failed` (CLI).
- Both storage backends' `connect()` create their client/engine with
  credential-safe logging in mind; `trutina-storage-postgres` additionally
  constructs its engine with `hide_parameters=True`, so a future SQLAlchemy
  exception never includes bound parameter values (account names, amounts).

## Tooling Commands

```bash
uv sync --all-packages
uv run pytest -m unit
uv run alembic -c packages/storage-postgres/alembic.ini upgrade head
uv run pytest -m integration          # requires PostgreSQL
uv run pytest -m "unit and cli"       # single layer, either axis
uv run pytest -m "integration and infra and mongo"    # single backend, infra layer only
uv run ruff check
uv run ruff format
uv run ty check
uv run lint-imports
```

`tools/bootstrap.sh` — sync workspace. `tools/fix.sh` — auto-fix format/lint.
`tools/pre-push.sh` — fast local gate (format check, lint, `ty check`, unit tests).
`tools/docker-build.sh` / `tools/docker-smoke.sh` — build/smoke-test the API image
against a real PostgreSQL container; the smoke test also asserts a structured
`request.completed` log line with a `correlation_id` appears in the container's output.

## Testing Layout

- Root `pytest.ini`: `testpaths = tests apps packages`, `asyncio_mode = auto`,
  markers `unit`/`integration` (speed, hand-written); `core`/`infra`/`cli`/`api`/
  `shared`/`config`/`observability` (layer, auto-derived from file path by root
  `conftest.py`); and `mongo`/`postgres` (backend, auto-derived, only meaningful
  for `infra`-layer tests). Collection fails loudly if a test hand-writes a
  conflicting layer or backend marker.
- Root `tests/{fixtures,factories,fakes}/` — shared test infrastructure only.
- Root `conftest.py` registers per-package fixture plugins (account, posting,
  journal, mongo, postgres, settings, services, cli, api, logging).
- `tests/fixtures/postgres.py`'s session-scoped `schema_init` applies the real
  Alembic migration history once per session, and re-enables every Python
  logger afterward — see Known Gaps below for why.

## Configuration

- `trutina.config`: `Settings` (prod, `TRUTINA_` prefix, `.env`), `TestSettings`
  (`TRUTINA_TEST_` prefix, `.env.test`), `MongoSettings`, `PostgresSettings`,
  `ApiSettings`, `LoggingSettings`, cached `get_settings()`.
- Nested env vars use double underscore: `TRUTINA_MONGO__URI`, `TRUTINA_POSTGRES__URI`,
  `TRUTINA_LOGGING__LEVEL`, and their `TRUTINA_TEST_` equivalents.
  `LOGGING__LOGGER_LEVELS` is overridden as a single JSON object, since the
  `__` delimiter would otherwise mangle logger names that contain dots.
- `get_settings()` is `lru_cache`d — tests must clear the cache before/after
  mutating environment variables (root `tests/fixtures/settings.py` does this
  automatically via an autouse fixture).
- `LoggingSettings.file_path` accepts either `str` or `pathlib.Path` — a
  `mode="before"` field validator coerces the latter, since Pydantic v2 does
  not do this implicitly and pytest's `tmp_path` fixture (among other
  callers) naturally returns a `Path`.

## Known Gaps / Cross-Package Flags (do not silently resolve — see PROJECT_CONTEXT.md)

- `trutina-shared` says `util.default_posting_date()` is unused; `apps/cli`'s
  journal parser visibly imports and calls it. Unresolved conflict.
- `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status not
  re-confirmed against current `trutina-core` source in this pass.
- `MongoPostingRepo.save_many()` has no multi-document transaction (accepted,
  documented risk in `trutina-storage-mongo`'s own CONTEXT.md; no longer
  app-facing since neither app depends on that package).
- Root `compose.yml`/`compose.dev.yml` provision only MongoDB, despite
  `apps/api`/`apps/cli` depending on `trutina-storage-postgres`.
- `TrialBalanceRepo` is implemented for PostgreSQL only. `trutina-storage-mongo` has
  no implementation, by decision.
- The trial balance lists only accounts with postings; full-chart, zero-padded output
  is not implemented.
- `trutina-cli`'s `--as-of` resolves to midnight, so postings stamped later that day
  are excluded. `trutina.core.trial_balance` is not named in any import-linter
  contract; it imports only `trutina.shared`.
- Alembic's own `env.py` calls `logging.config.fileConfig()` for
  `trutina-storage-postgres`'s migrations; that call now explicitly passes
  `disable_existing_loggers=False`, after a confirmed bug (found during Phase
  6's logging rollout verification) where the default `True` value silently
  disabled every already-instantiated, non-Alembic-declared Python logger for
  the rest of a test session — including this workspace's own
  `trutina.storage_postgres.shared.connection` logger. `tests/fixtures/postgres.py`'s
  `schema_init` also re-enables every logger after migrating, as a backstop.
  See `packages/storage-postgres/CONTEXT.md` for the full account.
- `tools/docker-smoke.sh` has been updated to assert structured logging output
  but has not yet been run end-to-end against the current image in this pass.

## Development Rules

- Keep business logic out of `trutina.cli`/`trutina.api`/either storage package —
  it belongs in `trutina.core` services and domain schemas only.
- Never let `trutina.core` import `beanie`, `pymongo`, `sqlalchemy`, `asyncpg`,
  `typer`, `rich`, `fastapi`, `structlog`, or `trutina.observability`.
- Never let `trutina.cli` and `trutina.api` import each other.
- Never let `trutina.shared`, `trutina.config`, `trutina.core`, or either storage
  package import `trutina.observability` or `structlog` — only `trutina.cli` and
  `trutina.api` may, each exactly once at their own composition root.
- Never let `trutina.observability` import `trutina.core`, either storage
  package, `fastapi`, `starlette`, `typer`, or `rich` — it must stay generic.
- A service logs its own success, never its own failure — a raised
  `AppError`/`ValidationAppError` is logged exactly once, by the catching
  presentation-layer seam (`error_boundary()` or the API's exception
  handlers), never by the service that raised it.
- Update a package's own README.md/CONTEXT.md when its structure or maturity
  changes; do not let root docs re-describe package internals.
- Do not document scaffolding, planned features, or unconfirmed facts as implemented.
- Docstrings and documentation describe Trutina's own design, behavior,
  responsibilities, invariants, and decisions only. Never state or imply that an
  implementation mirrors, copies, or matches another one, and never cite another
  adapter, package, or component as the reason for how something is written.
