from decimal import Decimal

import pytest
from trutina.cli.composition.actor import PRE_AUTH_ACTOR
from trutina.cli.composition.context import CliContext
from trutina.cli.features.journal.handler import (
    create_journal_entry_handler,
    get_journal_entry_handler,
    list_journal_entries_handler,
)
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.journal.dtos import JournalLineInput, JournalViewModel
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_create_journal_input,
    make_fake_account_repo,
)
from tests.factories.cli import make_fake_cli_context
from tests.fakes import FakeJournalRepo


def _simple_chart():
    """Cash/Sales Revenue chart -- matches make_create_journal_input()'s
    own default line accounts, and mirrors JournalService's test-suite
    helper of the same name.
    """
    return make_chart_of_accounts(
        accounts=[
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET),
            make_account(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        ]
    )


@pytest.fixture
def journal_cli_context() -> CliContext:
    """A fake CliContext whose account repo is seeded with Cash/Sales
    Revenue and whose journal repo starts empty.

    Handlers are plain async functions with no Typer/portal dependency,
    so they're exercised directly against a CliContext -- never through
    a CliState/BlockingPortal -- mirroring test_handler.py's account
    equivalent and its documented reasoning for why (cross-loop hazard
    between pytest-asyncio's loop and a fixture's own portal loop).

    Built locally rather than pulled from a shared fixture -- no
    "seeded, empty-journal" CliContext fixture is confirmed to exist
    yet for the Journal feature.
    """
    return make_fake_cli_context(chart=_simple_chart())


@pytest.mark.unit
class TestCreateJournalEntryHandler:
    async def test_returns_journal_view_model(self, journal_cli_context: CliContext):
        dto = make_create_journal_input()

        result = await create_journal_entry_handler(journal_cli_context, dto)

        assert isinstance(result, JournalViewModel)
        assert result.journal_number == 1
        assert result.is_balanced is True

    async def test_persists_entry_through_service(
        self, journal_cli_context: CliContext
    ):
        dto = make_create_journal_input()

        created = await create_journal_entry_handler(journal_cli_context, dto)

        service = await journal_cli_context.get_journal_service()
        fetched = await service.get_journal_entry(created.journal_number)
        assert fetched.journal_number == created.journal_number

    async def test_raises_unknown_account_for_unresolvable_line(
        self, journal_cli_context: CliContext
    ):
        dto = make_create_journal_input(
            lines=[
                JournalLineInput(account="Ghost Account", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await create_journal_entry_handler(journal_cli_context, dto)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT

    async def test_raises_validation_error_for_unbalanced_entry(
        self, journal_cli_context: CliContext
    ):
        dto = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("50")),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await create_journal_entry_handler(journal_cli_context, dto)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.unit
class TestGetJournalEntryHandler:
    async def test_returns_entry_after_creation(self, journal_cli_context: CliContext):
        dto = make_create_journal_input()
        created = await create_journal_entry_handler(journal_cli_context, dto)

        result = await get_journal_entry_handler(
            journal_cli_context, created.journal_number
        )

        assert result.journal_number == created.journal_number

    async def test_raises_unknown_journal_entry_when_missing(
        self, journal_cli_context: CliContext
    ):
        with pytest.raises(AppError) as exc_info:
            await get_journal_entry_handler(journal_cli_context, 999)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY


@pytest.mark.unit
class TestListJournalEntriesHandler:
    async def test_returns_empty_list_when_no_entries(
        self, journal_cli_context: CliContext
    ):
        result = await list_journal_entries_handler(journal_cli_context)

        assert result == []

    async def test_returns_created_entries_in_order(
        self, journal_cli_context: CliContext
    ):
        dto = make_create_journal_input()
        await create_journal_entry_handler(journal_cli_context, dto)
        await create_journal_entry_handler(journal_cli_context, dto)

        result = await list_journal_entries_handler(journal_cli_context)

        assert [vm.journal_number for vm in result] == [1, 2]


@pytest.mark.unit
class TestCreateJournalEntryHandlerAttribution:
    async def test_attributes_the_write_to_the_cli_pre_auth_actor(
        self, simple_chart, create_input
    ):
        journal_repo = FakeJournalRepo()
        ctx = CliContext(
            account_repo=make_fake_account_repo(chart=simple_chart),
            journal_repo=journal_repo,
        )

        await create_journal_entry_handler(ctx, create_input)

        assert journal_repo.saved_created_by == [PRE_AUTH_ACTOR]

    async def test_pre_auth_actor_names_the_cli(self):
        assert PRE_AUTH_ACTOR == "system:pre-auth:cli"
