# trutina-core

The double-entry accounting domain for Trutina: validated domain models, service
workflows, and repository contracts for accounts, journal entries, and ledger postings.

## What This Package Is

`trutina-core` owns the rules for what counts as a valid accounting transaction and
what happens when one is posted. It has no database driver, no HTTP framework, and no
CLI framework — pure business logic plus the repository interfaces storage adapters
must satisfy. It is consumed by `apps/cli` and `apps/api`; its repository contracts are
implemented by `trutina-storage-mongo`. Core itself never imports any of those three.

If a change is a rule about debits, credits, account codes, or posting derivation, it
belongs here. If it's about Mongo documents, Typer commands, or HTTP routes, it doesn't.

## Installation

Within the workspace:

```bash
uv sync --package trutina-core
```

`trutina-core` depends only on `trutina-shared` (validation helpers, the error model)
and `pydantic`. It has no dependency on `trutina-storage-mongo`, `trutina-config`,
`trutina-cli`, or `trutina-api` — confirmed in `packages/core/pyproject.toml`.

## Public API

Import from each feature's package root, not from internal submodules:

| Symbol                     | Package                | Purpose                                                 |
| -------------------------- | ---------------------- | ------------------------------------------------------- |
| `AccountService`           | `trutina.core.account` | Create/update/get/list/resolve/delete account workflows |
| `AccountRepo`              | `trutina.core.account` | Abstract persistence contract for `Account`             |
| `CreateAccountInput`       | `trutina.core.account` | Input DTO for account creation                          |
| `UpdateAccountInput`       | `trutina.core.account` | Input DTO for partial account updates                   |
| `AccountViewModel`         | `trutina.core.account` | Output view of a single account                         |
| `ChartOfAccountsViewModel` | `trutina.core.account` | Output view of every account                            |
| `JournalService`           | `trutina.core.journal` | Create/get/list journal-entry workflows                 |
| `JournalRepo`              | `trutina.core.journal` | Abstract persistence contract for `JournalEntry`        |
| `CreateJournalInput`       | `trutina.core.journal` | Input DTO for journal-entry creation                    |
| `JournalLineInput`         | `trutina.core.journal` | Input DTO for a single journal line                     |
| `JournalViewModel`         | `trutina.core.journal` | Output view of a journal entry                          |
| `JournalLineViewModel`     | `trutina.core.journal` | Output view of a journal line                           |
| `PostingService`           | `trutina.core.posting` | Post a journal entry; retrieve postings                 |
| `PostingRepo`              | `trutina.core.posting` | Abstract persistence contract for `LedgerPosting`       |
| `PostingViewModel`         | `trutina.core.posting` | Output view of a single posting (no input DTO exists)   |

Domain schemas (`Account`, `JournalEntry`, `JournalLine`, `LedgerPosting`,
`ChartOfAccounts`) are importable from their explicit submodule paths
(e.g. `trutina.core.account.schemas.account`) when a repository adapter or similar
needs the domain type itself. Callers outside `core` should generally work with DTOs
and ViewModels instead.

## Package Layout

```text
packages/core/src/trutina/core/
├── account/
│   ├── dtos.py          # CreateAccountInput, UpdateAccountInput, AccountViewModel, ChartOfAccountsViewModel
│   ├── repo.py           # AccountRepo — abstract persistence contract
│   ├── service.py        # AccountService — create/update/get/list/resolve/delete
│   └── schemas/
│       ├── account.py    # Account, AccountCategory
│       └── chart.py      # ChartOfAccounts
├── journal/
│   ├── dtos.py           # CreateJournalInput, JournalLineInput, JournalViewModel, JournalLineViewModel
│   ├── repo.py            # JournalRepo — abstract persistence contract
│   ├── service.py         # JournalService — create/get/list
│   └── schemas/
│       ├── journal.py     # JournalEntry
│       └── line.py        # JournalLine
└── posting/
    ├── dtos.py            # PostingViewModel (output-only — no input DTO)
    ├── repo.py             # PostingRepo — abstract persistence contract
    ├── service.py          # PostingService — post/get-by-account/get-by-journal-number
    └── schemas/
        └── ledger_posting.py  # LedgerPosting (frozen)
```

Each feature is self-contained: its own DTOs, repository contract, service, and
schemas. Tests live beside the code they cover (`account/tests/`, `journal/tests/`,
`posting/tests/`), split into `test_*_unit.py` (fake-repo, `@pytest.mark.unit`) and
`test_*_integration.py` (real MongoDB via `trutina-storage-mongo`,
`@pytest.mark.integration`).

## Usage

### Creating an account

```python
from trutina.core.account import AccountService, CreateAccountInput
from trutina.core.account.schemas.account import AccountCategory

service = AccountService(repo)  # repo: any AccountRepo implementation

account = await service.create_account(
    CreateAccountInput(code="1001", name="Cash", category=AccountCategory.ASSET)
)
# account.normal_balance == "debit"
```

### Creating a balanced journal entry

```python
from datetime import datetime
from decimal import Decimal
from trutina.core.journal import JournalService, CreateJournalInput, JournalLineInput

journal_service = JournalService(journal_repo, account_service)

entry = await journal_service.create_journal_entry(
    CreateJournalInput(
        posting_date=datetime(2025, 1, 1),
        lines=[
            JournalLineInput(account="Cash", debit_amount=Decimal("100.00")),
            JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100.00")),
        ],
        description="Cash sale",
    )
)
# entry.is_balanced == True
```

An unbalanced entry, an unknown account, or a future-dated entry raises before
anything is persisted — see [Error Handling](#error-handling).

### Posting a journal entry to the ledger

```python
from trutina.core.posting import PostingService

posting_service = PostingService(posting_repo, journal_service)

postings = await posting_service.post_journal_entry(entry.journal_number)
# one PostingViewModel per journal line; posting the same entry twice raises
```

## Integration With the Rest of the Repository

```text
apps/cli, apps/api
        │  (constructs concrete repos, injects into services)
        ▼
trutina-storage-mongo   (Mongo* repos implementing AccountRepo/JournalRepo/PostingRepo)
        │
        ▼
trutina-core             ← you are here
        │
        ▼
trutina-shared           (validation helpers, error model)
```

Core never imports `trutina-storage-mongo`, `trutina-cli`, or `trutina-api`. It is
handed a concrete repository at service-construction time by whichever app or
infrastructure layer wires the graph together — core has no opinion on what that
repository is backed by.

Internally, `posting` may import from `journal` and `account`; `journal` may import
from `account`; `account` may import from neither. This ordering is enforced by an
import-linter `layers` contract at the workspace root, not just by convention.

## Extending

Adding a new operation to an existing feature (e.g. a new `AccountService` method):

1. Add any new DTO/ViewModel fields to `dtos.py` first — service methods should
   accept and return DTOs, never raw domain objects, at the public boundary.
2. Add the repository method to the abstract `*Repo` class if new persistence access
   is needed, with a docstring describing the contract any adapter must satisfy.
3. Implement the service method. Construct domain schemas (`Account`,
   `JournalEntry`, etc.) inside the service — validation happens at construction time
   via Pydantic, and `ValidationError` should be caught and re-raised as
   `ValidationAppError`.
4. Add unit tests against a `Fake*Repo` (see [Testing](#testing)).

Adding a new feature module (e.g. a future `reporting` module):

1. Mirror the existing shape: `dtos.py`, `repo.py`, `service.py`, `schemas/`, `tests/`.
2. Respect the internal layering — a new module may depend on `account`, `journal`,
   or `posting` per the same rules those three already follow, but the import-linter
   contract must be updated if a new directional dependency is introduced.
3. Keep the module free of `beanie`/`pymongo` imports — the workspace-level
   import-linter contract enforces this for all of `trutina.core`.

## Testing

Run just this package's fast suite:

```bash
uv run pytest -m "unit and core"
```

Run its integration suite (requires MongoDB — see root `compose.yml` or
`.env.test.example`):

```bash
uv run pytest -m "integration and core"
```

When writing new service tests, substitute the repository with the matching
`Fake*Repo` from `tests/fakes/` rather than mocking — domain schemas should be
constructed directly with no mocking at all.

## Error Handling

Every error that can cross a service boundary is either `AppError` or its subclass
`ValidationAppError`, both from `trutina-shared`. Domain construction failures
(a Pydantic `ValidationError` raised by a schema) are caught by the service and
re-raised as `ValidationAppError`; business-rule failures (duplicate code, unknown
account, already-posted journal entry) are raised directly as `AppError` with a
specific `ErrorCode`.

Confirmed codes used by this package's services: `DUPLICATE_ACCOUNT_CODE`,
`DUPLICATE_ACCOUNT_NAME`, `UNKNOWN_ACCOUNT`, `UNKNOWN_JOURNAL_ENTRY`,
`JOURNAL_ALREADY_POSTED`, `VALIDATION_ERROR` (wrapping domain validators). Callers
should match on `AppError.code`, not on exception type alone, since every service
failure surfaces through the same two exception classes.

## What Consumers Should Know

- **Services are the only supported entry point.** Don't construct `Account`,
  `JournalEntry`, or `LedgerPosting` directly from outside this package — construct
  them through the corresponding service so validation and business rules run.
- **`CreateJournalInput` never carries a journal number.** `JournalService` assigns
  it via `JournalRepo.next_journal_number()`.
- **`PostingViewModel` has no matching input DTO.** Postings are always derived
  internally by `PostingService` from an already-persisted `JournalViewModel`.
- **Posting an entry twice raises, it doesn't silently no-op.** Callers must catch
  `AppError` with `ErrorCode.JOURNAL_ALREADY_POSTED` if retry logic is possible on
  their side.
- **Account name matching is case-insensitive** via `account_lookup_key()` in
  `trutina-shared`; display casing is preserved as originally entered.
