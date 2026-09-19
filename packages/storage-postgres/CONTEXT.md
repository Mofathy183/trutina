# trutina-storage-postgres context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

The core package defines storage-agnostic repository contracts and domain objects; this package supplies their PostgreSQL implementation. Keeping SQLAlchemy and asyncpg here prevents database concerns from crossing into core services or presentation applications.

## Design Decisions

Connections are verified with `SELECT 1` before their engine and session factory are handed to repositories. Connection-time operational failures become `AppError` values, and a failed verification disposes the engine before the error leaves the storage boundary.

Each repository operation opens a new asynchronous SQLAlchemy session from the supplied factory. `PostgresExecutor` centralizes translation of infrastructure failures, while repositories retain integrity errors long enough to map a violated constraint to the domain-specific error that has the required context.

Account names and posting account names are persisted with derived lookup-key columns. The repositories produce those keys with the shared Unicode-aware `account_lookup_key()` rule on every write, so PostgreSQL's case-insensitive uniqueness and lookup behavior follows the domain's rule.

Journal entries and their lines are explicitly inserted in one transaction, retaining input order through `line_index`. Posting batches are also committed as one transaction, and their `(journal_number, line_index)` uniqueness constraint is the database backstop for concurrent requests that both pass the service-level pre-check.

Journal number reservation advances the identity column's backing PostgreSQL sequence directly. PostgreSQL sequence advances are not rolled back, so a reserved number remains consumed even when no later journal entry is saved.

The trial balance is a report, not a stored resource, so `PostgresTrialBalanceRepo` owns no table and needs no migration. It runs one aggregation over `postings`: `SUM(debit_amount)` and `SUM(credit_amount)` grouped by `account_key`. Grouping on the lookup key merges postings recorded under different casings of one account name into a single row, and `MIN(account)` supplies a deterministic display name (the alphabetically-first recorded spelling). When an `as_of_date` is supplied, a `posting_date <= as_of_date` predicate scopes the rows; when it is `None`, every posting is included. Results are ordered ascending by display name. Every call recomputes from current rows; nothing is cached or materialized.

Only PostgreSQL implements the trial balance contract. `trutina-storage-mongo` has no `TrialBalanceRepo`, by decision: new features target PostgreSQL only.

## Invariants

Repositories reconstruct validated core domain objects when reading rows instead of returning persistence models. This makes corrupted data surface through domain validation rather than silently travelling to a caller. The trial balance follows the same rule: each aggregated row is rebuilt as an `AccountBalanceEntry`, so a blank or invalid account value fails validation instead of reaching a report.

No repository opens its own connection; construction requires the session factory from an already verified `PostgresConnection`. The connection bundle is immutable, and application shutdown disposes its engine and pooled connections together.

The trial balance repository never writes. It returns only accounts with at least one posting in scope, and an empty list when nothing is in scope.

## Control Flow

The composition root resolves PostgreSQL settings, verifies a connection, and gives its session factory plus an executor to each repository. A repository maps between core objects and SQLAlchemy models, commits or queries through the executor, then returns a core object or an `AppError` across the package boundary.

For a trial balance, `PostgresTrialBalanceRepo.get_account_balances()` builds the grouped statement, runs it through the executor in a fresh session, and maps each result row to an `AccountBalanceEntry`. Report-level totals and the balanced flag are derived later by `TrialBalanceService`, not here.

Alembic resolves its migration URL from the same settings types used at runtime. Passing `-x db=test` selects `TestSettings`, allowing migrations to target the test database without duplicating the connection URL in a second Alembic configuration.

## Known Gaps

If a journal-entry write collides with an existing journal number, the repository currently maps that conflict to `UNKNOWN_ERROR` because no dedicated error code exists. Normal callers obtain numbers from `next_journal_number()`, so the path is expected to be unreachable in ordinary use.

`PostgresExecutor` currently accepts a bare coroutine. Its shape may need to evolve to accept or hold an `AsyncSession` if the package introduces a shared session or unit-of-work scope, because SQLAlchemy's unit of work is session-scoped.

The trial balance aggregation scans every posting in scope on each call. `postings` is indexed on `account_key` but not on `posting_date`, so the `as_of_date` predicate is not index-assisted. This is acceptable at current ledger sizes and is tracked in `ROADMAP.md`.

`PostgresTrialBalanceRepo._to_domain()` lets a Pydantic `ValidationError` escape if a row fails `AccountBalanceEntry` validation; it is not translated to `AppError`. The same holds for the other repositories' row reconstruction.
