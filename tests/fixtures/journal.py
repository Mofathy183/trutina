from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.account.schemas import AccountCategory, ChartOfAccounts
from trutina.core.journal import (
    CreateJournalInput,
    JournalLineInput,
    JournalService,
)
from trutina.core.journal.schemas import JournalEntry, JournalLine

from tests.factories import (
    make_credit_line,
    make_debit_line,
    make_journal_entry,
    make_journal_service,
)
from tests.factories.account import make_account, make_chart_of_accounts
from tests.fakes import FakeJournalRepo


@pytest.fixture
def debit_line() -> JournalLine:
    return make_debit_line()


@pytest.fixture
def credit_line() -> JournalLine:
    return make_credit_line()


@pytest.fixture
def balanced_lines() -> list[JournalLine]:
    return [
        make_debit_line(amount=Decimal("100")),
        make_credit_line(amount=Decimal("100")),
    ]


@pytest.fixture
def journal_entry() -> JournalEntry:
    return make_journal_entry()


@pytest.fixture
def simple_chart() -> ChartOfAccounts:
    """Minimal chart with the two accounts used by default journal lines."""
    return make_chart_of_accounts(
        accounts=[
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET),
            make_account(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        ]
    )


@pytest.fixture
def journal_service(
    simple_chart: ChartOfAccounts,
) -> tuple[JournalService, FakeJournalRepo]:
    """A ready-to-use JournalService wired to a FakeJournalRepo and a
    FakeAccountRepo pre-seeded with Cash and Sales Revenue."""
    return make_journal_service(chart=simple_chart)


@pytest.fixture
def create_input() -> CreateJournalInput:
    """A valid CreateJournalInput that balances against simple_chart accounts."""
    return CreateJournalInput(
        posting_date=datetime(2025, 1, 1),
        lines=[
            JournalLineInput(account="Cash", debit_amount=Decimal("100")),
            JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
        ],
    )
