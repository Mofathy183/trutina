from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from trutina.core.account.schemas import AccountCategory, ChartOfAccounts
from trutina.core.journal import (
    CreateJournalInput,
    JournalLineInput,
    JournalRepo,
    JournalService,
)
from trutina.core.journal.schemas import JournalEntry, JournalLine
from trutina.storage_mongo.journal import MongoJournalRepo
from trutina.storage_mongo.shared import MongoExecutor

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


@pytest.fixture
def mongo_journal_repo(clean_db) -> JournalRepo:
    """A MongoJournalRepo instance backed by the clean test database.

    Declares ``clean_db`` as a dependency to guarantee:
    1. Beanie is initialized (``clean_db`` depends on ``beanie_init``).
    2. The database is empty before the test runs.

    Returns the abstract ``JournalRepo`` type so integration tests are
    written against the contract rather than the implementation.
    """

    return MongoJournalRepo(MongoExecutor())


@pytest.fixture
def stub_journal_document_settings(monkeypatch):
    """Allow JournalDocument construction without init_beanie().

    ``JournalDocument.__init__`` calls ``get_pymongo_collection()``, which
    raises ``CollectionWasNotInitialized`` unless Beanie has been initialized
    via ``init_beanie()``. ``MongoJournalRepo._to_document()`` and unit tests
    that use ``JournalDocument.model_construct()`` never perform I/O, so a
    stub settings object is sufficient to bypass the collection check.

    Mirrors the pattern of ``stub_account_document_settings``.
    """
    from trutina.storage_mongo.journal import JournalDocument

    monkeypatch.setattr(
        JournalDocument,
        "get_settings",
        classmethod[Any, [], SimpleNamespace](
            lambda cls: SimpleNamespace(pymongo_collection=None)
        ),
    )
