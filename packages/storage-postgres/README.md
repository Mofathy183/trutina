# trutina-storage-postgres

> Async PostgreSQL persistence adapters for Trutina's account, journal, and ledger-posting repository contracts.

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

| Symbol                | Purpose                                                   |
| --------------------- | --------------------------------------------------------- |
| `connect()`           | Creates a verified PostgreSQL engine and session factory. |
| `disconnect()`        | Disposes a connection bundle's engine and pool.           |
| `PostgresConnection`  | Immutable bundle of an async engine and session factory.  |
| `PostgresExecutor`    | Runs database work with infrastructure-error translation. |
| `PostgresAccountRepo` | Implements the core account repository contract.          |
| `PostgresJournalRepo` | Implements the core journal repository contract.          |
| `PostgresPostingRepo` | Implements the core posting repository contract.          |

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

## Testing

```bash
uv run pytest -m "unit and infra and postgres"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants, and known gaps.
- [trutina-core](../core/README.md) — repository contracts and domain objects implemented here.
- [trutina-config](../config/README.md) — typed PostgreSQL connection settings.
- [trutina-shared](../shared/README.md) — shared error types and account lookup rules.
