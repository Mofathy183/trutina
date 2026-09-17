# trutina-storage-mongo

> MongoDB and Beanie adapters that persist Trutina accounts, journal entries, and ledger postings.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-storage-informational)

## Quick Start

```bash
uv sync --package trutina-storage-mongo
uv run python -c "from trutina.storage_mongo import MongoConnection; print(MongoConnection)"
```

## What This Is

`trutina-storage-mongo` implements the `AccountRepo`, `JournalRepo`, and `PostingRepo` contracts from `trutina-core` with MongoDB and Beanie. It provides connection helpers, Beanie document models, and concrete repositories for use at an application's composition root. For design decisions, invariants, and accepted risks, see [CONTEXT.md](CONTEXT.md).

## API at a Glance

| Symbol                                                  | Purpose                                                                    |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| `MongoConnection`                                       | Immutable bundle of a verified async MongoDB client and selected database. |
| `connect()` / `disconnect()`                            | Open a ping-verified connection and close its client.                      |
| `MongoExecutor`                                         | Executes Beanie operations with MongoDB error translation.                 |
| `MongoAccountRepo`                                      | `AccountRepo` implementation for the `accounts` collection.                |
| `MongoJournalRepo`                                      | `JournalRepo` implementation for journal entries and number allocation.    |
| `MongoPostingRepo`                                      | `PostingRepo` implementation for ledger postings.                          |
| `AccountDocument`, `JournalDocument`, `PostingDocument` | Beanie document models registered before repositories are used.            |
| `TimestampedDocument`                                   | Shared Beanie document base with insert timestamps.                        |

## Usage

Initialize Beanie after connecting, then construct the repositories in the same application lifecycle:

```python
import asyncio

from beanie import init_beanie
from trutina.config import get_settings
from trutina.storage_mongo import connect, disconnect
from trutina.storage_mongo.account import AccountDocument, MongoAccountRepo
from trutina.storage_mongo.journal import JournalDocument, MongoJournalRepo
from trutina.storage_mongo.posting import PostingDocument, MongoPostingRepo
from trutina.storage_mongo.shared import MongoExecutor


async def main() -> None:
    connection = await connect(get_settings().mongo)
    try:
        await init_beanie(
            database=connection.db,
            document_models=[AccountDocument, JournalDocument, PostingDocument],
        )
        executor = MongoExecutor()
        account_repo = MongoAccountRepo(executor)
        journal_repo = MongoJournalRepo(executor)
        posting_repo = MongoPostingRepo(executor)
    finally:
        await disconnect(connection)


asyncio.run(main())
```

Use a repository through its core contract after initialization:

```python
import asyncio

from beanie import init_beanie
from trutina.config import get_settings
from trutina.storage_mongo import connect, disconnect
from trutina.storage_mongo.account import AccountDocument, MongoAccountRepo
from trutina.storage_mongo.journal import JournalDocument
from trutina.storage_mongo.posting import PostingDocument
from trutina.storage_mongo.shared import MongoExecutor


async def main() -> None:
    connection = await connect(get_settings().mongo)
    try:
        await init_beanie(
            database=connection.db,
            document_models=[AccountDocument, JournalDocument, PostingDocument],
        )
        account_repo = MongoAccountRepo(MongoExecutor())
        account = await account_repo.get_by_code("1001")
        print(account)
    finally:
        await disconnect(connection)


asyncio.run(main())
```

## Testing

```bash
uv run pytest -m "unit and infra and mongo"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants, and known risks.
- [trutina-core](../core/README.md) — repository contracts and accounting services.
- [trutina-config](../config/README.md) — `MongoSettings` used by `connect()`.
