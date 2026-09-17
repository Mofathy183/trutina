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

## Invariants

Repositories reconstruct validated core domain objects when reading rows instead of returning persistence models. This makes corrupted data surface through domain validation rather than silently travelling to a caller.

No repository opens its own connection; construction requires the session factory from an already verified `PostgresConnection`. The connection bundle is immutable, and application shutdown disposes its engine and pooled connections together.

## Control Flow

The composition root resolves PostgreSQL settings, verifies a connection, and gives its session factory plus an executor to each repository. A repository maps between core objects and SQLAlchemy models, commits or queries through the executor, then returns a core object or an `AppError` across the package boundary.

Alembic resolves its migration URL from the same settings types used at runtime. Passing `-x db=test` selects `TestSettings`, allowing migrations to target the test database without duplicating the connection URL in a second Alembic configuration.

## Known Gaps

If a journal-entry write collides with an existing journal number, the repository currently maps that conflict to `UNKNOWN_ERROR` because no dedicated error code exists. Normal callers obtain numbers from `next_journal_number()`, so the path is expected to be unreachable in ordinary use.

`PostgresExecutor` currently accepts a bare coroutine. Its shape may need to evolve to accept or hold an `AsyncSession` if the package introduces a shared session or unit-of-work scope, because SQLAlchemy's unit of work is session-scoped.
