# trutina-infrastructure

Concrete MongoDB/Beanie storage adapters for Trutina's accounting domain.

## What Is This

`trutina-infrastructure` (import path `trutina.infrastructure`) implements
the repository contracts defined in `trutina-core` (`AccountRepo`,
`JournalRepo`, `PostingRepo`) against MongoDB, and provides the connection
lifecycle and error-translation utilities every adapter relies on. This is
the only package in the workspace that imports `beanie` or `pymongo`.

It contains no accounting rules, business validation, or uniqueness
pre-checks — those belong to `trutina-core`'s services and domain schemas.

### Package Layout

```text
packages/infrastructure/src/trutina/infrastructure/
├── __init__.py                    # empty
└── mongo/
    ├── __init__.py                # MongoConnection, connect, disconnect
    ├── connection.py
    ├── error_translation.py       # translate_mongo_errors(), violated_index() — not re-exported
    ├── shared/
    │   ├── document.py            # TimestampedDocument
    │   ├── repository.py          # MongoExecutor
    │   └── tests/
    ├── account/
    │   ├── document.py            # AccountDocument
    │   ├── repository.py          # MongoAccountRepo
    │   └── tests/
    ├── journal/
    │   ├── document.py            # JournalDocument, JournalLineSubDocument
    │   ├── repository.py          # MongoJournalRepo
    │   └── tests/
    └── posting/
        ├── document.py            # PostingDocument
        ├── repository.py          # MongoPostingRepo
        └── tests/
```

## Installation

From the workspace root:

```bash
uv sync --package trutina-infrastructure
```

or `uv sync` to install the whole workspace.

## Public API

| Symbol                                             | Module                                 | Purpose                                                                  |
| -------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------ |
| `MongoConnection`                                  | `trutina.infrastructure.mongo`         | Immutable bundle of a verified MongoDB client and the selected database. |
| `connect(mongo: MongoSettings) -> MongoConnection` | `trutina.infrastructure.mongo`         | Opens a MongoDB client and verifies it with a ping before returning.     |
| `disconnect(connection: MongoConnection) -> None`  | `trutina.infrastructure.mongo`         | Closes the client held by a `MongoConnection`.                           |
| `TimestampedDocument`                              | `trutina.infrastructure.mongo.shared`  | Base Beanie document; sets `created_at`/`updated_at` via an insert hook. |
| `MongoExecutor`                                    | `trutina.infrastructure.mongo.shared`  | Runs a Beanie coroutine through `translate_mongo_errors()`.              |
| `AccountDocument`                                  | `trutina.infrastructure.mongo.account` | Beanie document for the `accounts` collection.                           |
| `MongoAccountRepo`                                 | `trutina.infrastructure.mongo.account` | Concrete `AccountRepo` implementation.                                   |
| `JournalDocument`                                  | `trutina.infrastructure.mongo.journal` | Beanie document for the `journal_entries` collection.                    |
| `JournalLineSubDocument`                           | `trutina.infrastructure.mongo.journal` | Embedded subdocument for a single journal line.                          |
| `MongoJournalRepo`                                 | `trutina.infrastructure.mongo.journal` | Concrete `JournalRepo` implementation.                                   |
| `PostingDocument`                                  | `trutina.infrastructure.mongo.posting` | Beanie document for the `postings` collection.                           |
| `MongoPostingRepo`                                 | `trutina.infrastructure.mongo.posting` | Concrete `PostingRepo` implementation.                                   |

`error_translation.py` (`translate_mongo_errors`, `violated_index`) is used
internally by every repository and by `MongoExecutor`. It is not
re-exported from any package `__init__.py` — import it directly from
`trutina.infrastructure.mongo.error_translation` if you need it.

## Usage

### Opening a connection

```python
from trutina.config import get_settings
from trutina.infrastructure.mongo import connect, disconnect

settings = get_settings()
connection = await connect(settings.mongo)  # verifies connectivity with a ping
...
await disconnect(connection)
```

### Wiring a repository

Every concrete repository takes a `MongoExecutor`, not a raw client or
database handle. `init_beanie()` must run before any repository is
constructed — every repository assumes its `Document` class is already
registered.

```python
from beanie import init_beanie
from trutina.infrastructure.mongo import connect
from trutina.infrastructure.mongo.account import AccountDocument, MongoAccountRepo
from trutina.infrastructure.mongo.journal import JournalDocument
from trutina.infrastructure.mongo.posting import PostingDocument
from trutina.infrastructure.mongo.shared import MongoExecutor

connection = await connect(settings.mongo)
await init_beanie(
    database=connection.db,
    document_models=[AccountDocument, JournalDocument, PostingDocument],
)

executor = MongoExecutor()
account_repo = MongoAccountRepo(executor)
```

### Using a repository

Callers consume repositories through the `AccountRepo`/`JournalRepo`/
`PostingRepo` contracts from `trutina-core`, so calling code only needs to
import the concrete `Mongo*Repo` classes at composition time:

```python
account = await account_repo.get_by_code("1001")
```

## Integration

- **Consumers:** `apps/cli` and `apps/api` each construct these repositories
  in their own composition root (`CliContext`, the API's `bootstrap.py`),
  then hand them to `trutina-core` services.
- **Never a consumer of:** `apps/cli` or `apps/api` — enforced by the root
  workspace's `layers` import-linter contract
  (`trutina.cli | trutina.api → trutina.infrastructure → trutina.core →
trutina.shared | trutina.config`).
- **Depends on** (per `packages/infrastructure/pyproject.toml`):
  `trutina-shared`, `trutina-core`, `trutina-config`, `beanie`, `pymongo`.

## Extending — adding a new bounded-context adapter

Follow the shape already established by `account`/`journal`/`posting`:

1. Add `mongo/<feature>/document.py` — a `TimestampedDocument` subclass (or
   `pydantic.BaseModel` for embedded subdocuments) with a `Settings` class
   declaring the collection name and indexes.
2. Add `mongo/<feature>/repository.py` — a `Mongo<Feature>Repo` implementing
   the corresponding `trutina-core` repo contract, built around a single
   `_to_document()`/`_to_domain()` mapping boundary and a `MongoExecutor`.
3. Add `mongo/<feature>/__init__.py` re-exporting the document(s) and repo.
4. Register the new `Document` class wherever `init_beanie()` is called in
   production, and add it to `tests/fixtures/mongo.py::DOCUMENT_MODELS` so
   integration tests pick it up.
5. Add `mongo/<feature>/tests/test_document.py`, `test_repository_unit.py`
   (pure mapping logic, no I/O), and `test_repository_integration.py` (real
   MongoDB, `@pytest.mark.integration`).

## Testing

- **Unit tests** live beside each adapter under `mongo/<feature>/tests/`
  (plus `mongo/tests/` for `connection.py`/`error_translation.py`) and
  never touch a real database. Document construction is exercised via
  `Document.model_construct(...)` or a `stub_*_document_settings` fixture
  that patches `get_settings()` so `Document.__init__` doesn't require
  `init_beanie()` to have run.
- **Integration tests** (`test_repository_integration.py`, marked
  `@pytest.mark.integration`) run against a real MongoDB instance via the
  `mongo_connection` → `beanie_init` → `clean_db` → `mongo_<feature>_repo`
  fixture chain in `tests/fixtures/`. `clean_db` truncates collections
  between tests rather than dropping them, so indexes survive the whole
  session.
- Run just this package's tests with `pytest -m "unit and infra"` /
  `pytest -m "integration and infra"` (the `infra` marker is derived
  automatically from file path by the root `conftest.py`).

## Known Limitations

- `MongoPostingRepo.save_many()` writes its batch with a single
  `insert_many()` and no `ClientSession` — there is no multi-document
  transaction support anywhere in this package today. A mid-batch
  interruption can partially persist a journal's postings, and two
  concurrent posting attempts for the same journal number can both pass
  `PostingService`'s pre-check before either writes.
- There is no second storage backend yet — every repository contract
  currently has exactly one concrete implementation, this one.
