# trutina-storage-postgres

> Async PostgreSQL persistence adapters for Trutina's account, journal, ledger-posting, and trial balance repository contracts.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-storage-informational)

## Quick Start

```bash
uv sync --all-packages
$env:TRUTINA_POSTGRES__URI = "postgresql+asyncpg://localhost:5432/trutina"
uv run alembic -c packages/storage-postgres/alembic.ini upgrade head
uv run pytest -m "unit and infra and postgres"
```

## What This Is

`trutina-storage-postgres` implements the repository interfaces defined by `trutina-core` using SQLAlchemy's asynchronous PostgreSQL support. It consumes PostgreSQL settings from `trutina-config` and is the persistence layer beneath the presentation applications. For the design rationale, trade-offs, and known gaps, see [CONTEXT.md](CONTEXT.md).

## API at a Glance

| Symbol                     | Purpose                                                                         |
| -------------------------- | ------------------------------------------------------------------------------- |
| `connect()`                | Creates a verified PostgreSQL engine and session factory. Logs `db.connected`.  |
| `disconnect()`             | Disposes a connection bundle's engine and pool. Logs `db.disconnected`.         |
| `PostgresConnection`       | Immutable bundle of an async engine and session factory.                        |
| `PostgresExecutor`         | Runs database work with infrastructure-error translation.                       |
| `PostgresAccountRepo`      | Implements the core account repository contract.                                |
| `PostgresJournalRepo`      | Implements the core journal repository contract.                                |
| `PostgresPostingRepo`      | Implements the core posting repository contract.                                |
| `PostgresTrialBalanceRepo` | Implements the core trial balance contract by aggregating the `postings` table. |

## Usage

Create a verified connection, construct a repository with its session factory, and close the pool when the application stops:

```python
import asyncio

from trutina.config import Settings
from trutina.core.account.schemas.account import Account, AccountCategory
from trutina.storage_postgres.account import PostgresAccountRepo
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


async def main() -> None:
    connection = await connect(Settings().postgres)
    repository = PostgresAccountRepo(connection.session_factory, PostgresExecutor())
    try:
        await repository.create(
            Account(code="1000", name="Cash", category=AccountCategory.ASSET)
        )
    finally:
        await disconnect(connection)


asyncio.run(main())
```

Use the same connection bundle to assemble the journal and posting adapters:

```python
import asyncio

from trutina.config import Settings
from trutina.storage_postgres.journal import PostgresJournalRepo
from trutina.storage_postgres.posting import PostgresPostingRepo
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor


async def main() -> None:
    connection = await connect(Settings().postgres)
    executor = PostgresExecutor()
    try:
        journal_repository = PostgresJournalRepo(connection.session_factory, executor)
        posting_repository = PostgresPostingRepo(connection.session_factory, executor)
        journal_number = await journal_repository.next_journal_number()
        print(journal_number, posting_repository)
    finally:
        await disconnect(connection)


asyncio.run(main())
```

Read per-account debit and credit totals from posted entries. The trial balance repository is read-only and needs no migration, because it aggregates the existing `postings` table:

```python
import asyncio

from trutina.config import Settings
from trutina.storage_postgres.shared import connect, disconnect
from trutina.storage_postgres.shared.execution import PostgresExecutor
from trutina.storage_postgres.trial_balance import PostgresTrialBalanceRepo


async def main() -> None:
    connection = await connect(Settings().postgres)
    try:
        repository = PostgresTrialBalanceRepo(
            connection.session_factory, PostgresExecutor()
        )
        for entry in await repository.get_account_balances():
            print(entry.account, entry.debit_total, entry.credit_total)
    finally:
        await disconnect(connection)


asyncio.run(main())
```

## Attribution

`journal_entries` and `postings` carry a nullable `created_by` column. `PostgresJournalRepo.save()` and `PostgresPostingRepo.save_many()` take a keyword-only `created_by` and store it as given: once on the entry row, and on every posting row in a batch. Journal lines inherit their entry's attribution and have no column of their own. A null value means the row was written before attribution existed. `created_by` is not part of any core domain model, so repository reads never return it; read it with SQL. See [CONTEXT.md](CONTEXT.md) for why.

## Logging

`connect()` and `disconnect()` each emit one `logging.getLogger(__name__)` line — `db.connected` and `db.disconnected` — through Python's standard library only; this package imports nothing from `trutina-observability` or `structlog`. `db.connected`'s context carries `backend`, `pool_size`, `max_overflow`, and `pool_pre_ping` — never `postgres.uri`, since the URI can embed credentials. The engine itself is constructed with `hide_parameters=True`, so any exception SQLAlchemy raises omits bound parameter values (account names, amounts, etc.) from its text, independent of what any caller does with the exception afterward. See [CONTEXT.md](CONTEXT.md) for the full rationale and the Alembic logging caveat below.

## Testing

```bash
uv run pytest -m "unit and infra and postgres"
uv run pytest -m "integration and infra and postgres"
```

Integration tests apply the real Alembic migration history once per session (`tests/fixtures/postgres.py`'s `schema_init`) rather than `Base.metadata.create_all()`, so a migration that doesn't actually reproduce `models.py` fails as a test, not as a surprise the first time someone runs `alembic upgrade head` against a real environment. Alembic's own `env.py` is configured with `disable_existing_loggers=False` — see CONTEXT.md's Known Gaps for why that flag matters here specifically.

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants, and known gaps.
- [trutina-core](../core/README.md) — repository contracts and domain objects implemented here.
- [trutina-config](../config/README.md) — typed PostgreSQL connection settings.
- [trutina-shared](../shared/README.md) — shared error types and account lookup rules.
- [trutina-observability](../observability/README.md) — this package emits through stdlib `logging` only; observability owns how those records are formatted and routed.
