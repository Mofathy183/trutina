# trutina-core

> The double-entry accounting domain: it validates accounts and journal entries, then derives ledger postings.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-core-informational)

## Quick Start

```bash
uv sync --package trutina-core
uv run python -c "from trutina.core.account import AccountService; print(AccountService.__name__)"
uv run pytest -m "unit and core"
```

## What This Is

`trutina-core` provides service workflows, validated domain models, and abstract repository contracts for accounts, journal entries, and ledger postings. It depends only on Pydantic and `trutina-shared`; applications and storage adapters supply concrete repositories when constructing its services.

For design rationale, invariants, and dependency rules, see [CONTEXT.md](CONTEXT.md).

## API at a Glance

| Symbol group                    | Import path            | Purpose                                                              |
| ------------------------------- | ---------------------- | -------------------------------------------------------------------- |
| Account service and repository  | `trutina.core.account` | Create, update, fetch, list, resolve, and delete accounts.           |
| Account input and output models | `trutina.core.account` | `CreateAccountInput`, `UpdateAccountInput`, and account view models. |
| Journal service and repository  | `trutina.core.journal` | Create, fetch, and list journal entries.                             |
| Journal input and output models | `trutina.core.journal` | `CreateJournalInput`, `JournalLineInput`, and journal view models.   |
| Posting service and repository  | `trutina.core.posting` | Post a journal entry and retrieve its ledger postings.               |
| Posting output model            | `trutina.core.posting` | `PostingViewModel` for derived, immutable postings.                  |

Services take their matching abstract repository contract at construction time. Domain schemas are available from each feature's `schemas` package when an adapter needs the underlying domain types.

## Usage

Build an account-creation input before passing it to an `AccountService` constructed with an `AccountRepo` implementation:

```python
from trutina.core.account import CreateAccountInput
from trutina.core.account.schemas.account import AccountCategory

cash = CreateAccountInput(code="1001", name="Cash", category=AccountCategory.ASSET)
```

Create a balanced journal input with at least two lines, then pass it to `JournalService.create_journal_entry`:

```python
from datetime import datetime
from decimal import Decimal
from trutina.core.journal import CreateJournalInput, JournalLineInput

sale = CreateJournalInput(
    posting_date=datetime(2025, 1, 1),
    lines=[
        JournalLineInput(account="Cash", debit_amount=Decimal("100.00")),
        JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100.00")),
    ],
)
```

Use a `PostingService` to derive postings from a persisted journal entry:

```python
async def post_entry(posting_service):
    postings = await posting_service.post_journal_entry(journal_number=1)
    return [(posting.account, posting.is_debit) for posting in postings]
```

## Testing

```bash
uv run pytest -m "unit and core"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, and invariants.
- [`trutina-shared`](../shared/README.md) — validation helpers and the shared error model.
- [`trutina-storage-mongo`](../storage-mongo/README.md) — repository implementations.
- [`trutina-storage-postgres`](../storage-postgres/README.md) — repository implementations.
- [root README](../../README.md) — workspace setup and cross-package information.
