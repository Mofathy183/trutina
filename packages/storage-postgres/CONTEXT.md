# trutina-storage-postgres context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

The core package defines storage-agnostic repository contracts and domain objects; this package supplies their PostgreSQL implementation. Keeping SQLAlchemy and asyncpg here prevents database concerns from crossing into core services or presentation applications.

## Design Decisions

Connections are verified with `SELECT 1` before their engine and session factory are handed to repositories. Connection-time operational failures become `AppError` values, and a failed verification disposes the engine before the error leaves the storage boundary.

Each repository operation opens a new asynchronous SQLAlchemy session from the supplied factory. `PostgresExecutor` centralizes translation of infrastructure failures, while repositories retain integrity errors long enough to map a violated constraint to the domain-specific error that has the required context.

Account names and posting account names are persisted with derived lookup-key columns. The repositories produce those keys with the shared Unicode-aware `account_lookup_key()` rule on every write, so PostgreSQL's case-insensitive uniqueness and lookup behavior follows the domain's rule.

Journal entries and their lines are explicitly inserted in one transaction, retaining input order through `line_index`. Posting batches are also committed as one transaction, and their `(journal_number, line_index)` uniqueness constraint is the database backstop for concurrent requests that both pass the service-level pre-check.

Attribution is stored as a nullable `created_by` text column on `journal_entries` and `postings`. It is nullable because rows written before M1a have no actor and cannot be backfilled; null means pre-attribution, and system writers use explicit values such as `system:pre-auth:api`. It is written on the entry row only, not per journal line, because lines are inserted in the same transaction as their entry and inherit its attribution. Postings carry it on every row because they are the ledger's immutable record. There is no foreign key, because the value is an opaque string supplied by the calling application, not a reference to a users table. `_to_domain()` never reads it, since it is not part of `JournalEntry` or `LedgerPosting`.

Journal number reservation advances the identity column's backing PostgreSQL sequence directly. PostgreSQL sequence advances are not rolled back, so a reserved number remains consumed even when no later journal entry is saved.

The trial balance is a report, not a stored resource, so `PostgresTrialBalanceRepo` owns no table and needs no migration. It runs one aggregation over `postings`: `SUM(debit_amount)` and `SUM(credit_amount)` grouped by `account_key`. Grouping on the lookup key merges postings recorded under different casings of one account name into a single row, and `MIN(account)` supplies a deterministic display name (the alphabetically-first recorded spelling). When an `as_of_date` is supplied, a `posting_date <= as_of_date` predicate scopes the rows; when it is `None`, every posting is included. Results are ordered ascending by display name. Every call recomputes from current rows; nothing is cached or materialized.

Only PostgreSQL implements the trial balance contract. `trutina-storage-mongo` has no `TrialBalanceRepo`, by decision: new features target PostgreSQL only.

## Logging

`connect()` and `disconnect()` (`shared/connection.py`) each emit exactly one INFO line through `logging.getLogger(__name__)` — `db.connected` and `db.disconnected` — via the standard library only. This module imports nothing from `trutina.observability` or `structlog`, consistent with every emitter across the workspace: this package decides _that_ something happened, never _how_ it's formatted or _where_ it's routed.

`db.connected`'s context is deliberately narrow: `backend`, `pool_size`, `max_overflow`, `pool_pre_ping`. `postgres.uri` is never logged, because it can embed credentials directly (`postgresql+asyncpg://user:pass@host/db`). This mirrors `trutina-storage-mongo`'s identical rule for `mongo.uri`.

The engine is constructed with `hide_parameters=True`. SQLAlchemy then omits bound parameter values from the text of any exception it raises, so a future query failure's exception text never includes an account name, code, or amount — a property of the engine itself, independent of whatever a caller later does with that exception (log it, wrap it, discard it).

`PostgresExecutor` does not log failures itself; it continues to attach `cause` to the translated `AppError` and lets the calling seam (an API exception handler, the CLI's `error_boundary()`) log it exactly once. This is unchanged by the logging rollout and matches the "log where the error is handled, not where it is raised" principle stated at the workspace level.

### Known Gap Closed: Alembic's `fileConfig()` Silently Disabled Every Non-Alembic Logger

**Symptom, as originally observed:** `test_connection_logging.py`'s two `db.connected`-assertion tests passed every time the file was run alone, and failed with `RuntimeError: coroutine raised StopIteration` every time the file ran as part of the full `integration and infra and postgres` suite.

**Root cause:** the session-scoped `schema_init` fixture (`tests/fixtures/postgres.py`) runs `alembic upgrade head` once per session, ahead of every other Postgres-backed integration test. Alembic's generated `env.py` contains the standard

```python
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
```

`fileConfig()` defaults to `disable_existing_loggers=True` — this is Python's own `logging.config` behavior, not an Alembic bug. It sets `.disabled = True` on **every** `Logger` object already instantiated in the process that isn't explicitly named in the `[loggers]` section of `alembic.ini`. This package's `alembic.ini` names only `root`, `sqlalchemy`, `alembic`. `trutina.storage_postgres.shared.connection`'s module-level `logger = logging.getLogger(__name__)` object already existed (instantiated at import time, well before the first migration-dependent test ran), so the very first `schema_init` invocation in a session silently and permanently disabled it. Every subsequent `logger.info("db.connected", ...)` call became a silent no-op for the rest of that process — not filtered by level, not dropped by a missing handler, disabled at the `Logger` object itself.

**Fix, in two parts:**

1. **Primary fix, in `alembic/env.py`:**

```python
   if config.config_file_name is not None:
       fileConfig(config.config_file_name, disable_existing_loggers=False)
```

`root`/`sqlalchemy`/`alembic` are still configured exactly as `alembic.ini` specifies; every other already-instantiated logger in the process is simply left alone rather than disabled.

2. **Belt-and-braces insurance, in `tests/fixtures/postgres.py`'s `schema_init`:** immediately after `command.upgrade()` returns, every logger currently known to `logging.Logger.manager.loggerDict` is explicitly re-enabled (`.disabled = False`), as a backstop against the same class of bug from some other tool in the future — not a substitute for the `env.py` fix, since that backstop only runs inside this test fixture, not in any real (non-test) invocation of Alembic.

**Confirmed fixed:** `pytest -m "integration and infra and postgres"` passes 45/45, including all three `test_connection_logging.py` cases, run as part of the full suite rather than standalone.

**Why this matters beyond the test suite:** the underlying behavior — `fileConfig(disable_existing_loggers=True)` disabling arbitrary application loggers — is a property of _any_ process that calls Alembic's `env.py` programmatically, not just pytest. A future operational tool that invokes migrations in-process (rather than via the standalone `alembic` CLI) would have hit the identical silent-logging-loss failure mode in production. The `env.py` fix closes that path, not just the test's symptom.

## Invariants

Repositories reconstruct validated core domain objects when reading rows instead of returning persistence models. This makes corrupted data surface through domain validation rather than silently travelling to a caller. The trial balance follows the same rule: each aggregated row is rebuilt as an `AccountBalanceEntry`, so a blank or invalid account value fails validation instead of reaching a report.

No repository opens its own connection; construction requires the session factory from an already verified `PostgresConnection`. The connection bundle is immutable, and application shutdown disposes its engine and pooled connections together.

The trial balance repository never writes. It returns only accounts with at least one posting in scope, and an empty list when nothing is in scope.

## Control Flow

The composition root resolves PostgreSQL settings, verifies a connection, and gives its session factory plus an executor to each repository. A repository maps between core objects and SQLAlchemy models, commits or queries through the executor, then returns a core object or an `AppError` across the package boundary.

For a trial balance, `PostgresTrialBalanceRepo.get_account_balances()` builds the grouped statement, runs it through the executor in a fresh session, and maps each result row to an `AccountBalanceEntry`. Report-level totals and the balanced flag are derived later by `TrialBalanceService`, not here.

Alembic resolves its migration URL from the same settings types used at runtime. Passing `-x db=test` selects `TestSettings`, allowing migrations to target the test database without duplicating the connection URL in a second Alembic configuration. `env.py`'s `fileConfig()` call configures Python's stdlib `logging` module from `alembic.ini`'s `[loggers]`/`[handlers]`/`[formatters]` sections, with `disable_existing_loggers=False` — see the Known Gap Closed section above.

## Known Gaps

If a journal-entry write collides with an existing journal number, the repository currently maps that conflict to `UNKNOWN_ERROR` because no dedicated error code exists. Normal callers obtain numbers from `next_journal_number()`, so the path is expected to be unreachable in ordinary use.

`PostgresExecutor` currently accepts a bare coroutine. Its shape may need to evolve to accept or hold an `AsyncSession` if the package introduces a shared session or unit-of-work scope, because SQLAlchemy's unit of work is session-scoped.

The trial balance aggregation scans every posting in scope on each call. `postings` is indexed on `account_key` but not on `posting_date`, so the `as_of_date` predicate is not index-assisted. This is acceptable at current ledger sizes and is tracked in `ROADMAP.md`.

`PostgresTrialBalanceRepo._to_domain()` lets a Pydantic `ValidationError` escape if a row fails `AccountBalanceEntry` validation; it is not translated to `AppError`. The same holds for the other repositories' row reconstruction.

No test yet forces a real constraint-violation exception (e.g. a duplicate account code write) and asserts the resulting exception's `str()` contains no leaked account code/name — `hide_parameters=True` is confirmed _set_ on the engine (`test_engine_is_created_with_hide_parameters`), but its actual masking effect on a real exception's text is not yet directly exercised by a test. Tracked as a small Phase 7 addition.

`created_by` is nullable with no CHECK constraint and no index. Nothing stops a writer from passing a value the calling application would consider malformed, because format validation is deferred to the API and CLI handlers (M4b). Revisit a CHECK constraint on rows after a cutoff date once real identities exist.

## Allowed and Forbidden Dependencies

**Allowed** (per `pyproject.toml`): `trutina-shared`, `trutina-core`, `trutina-config`, `sqlalchemy`, `asyncpg`, `alembic`.

**Forbidden:** `trutina-cli`, `trutina-api`, `trutina-storage-mongo`, `trutina-observability`, `structlog`, or any presentation library. This package emits through `logging.getLogger(__name__)` only, enforced by the "Emitters use stdlib logging only" import-linter contract — it must never import `trutina.observability` or `structlog` directly.
