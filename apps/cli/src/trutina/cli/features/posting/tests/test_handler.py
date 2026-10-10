import pytest
import pytest_asyncio
from trutina.cli.composition import CliContext
from trutina.cli.composition.actor import PRE_AUTH_ACTOR
from trutina.cli.features.posting.handler import (
    get_postings_by_account_handler,
    get_postings_by_journal_number_handler,
    post_journal_entry_handler,
)
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.posting.dtos import PostingViewModel
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_fake_account_repo,
    make_fake_journal_repo,
    make_fake_posting_repo,
    make_journal_entry,
)
from tests.factories.actor import TEST_ACTOR
from tests.factories.cli import make_fake_cli_context
from tests.fakes import FakeJournalRepo, FakePostingRepo


def _simple_chart():
    return make_chart_of_accounts(
        accounts=[
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET),
            make_account(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        ]
    )


@pytest_asyncio.fixture
async def journal_cli_context():
    """CliContext with one unposted journal entry (#1) pre-saved directly
    to a FakeJournalRepo, and an empty FakePostingRepo.

    Built locally rather than as a shared fixture -- no other feature's
    tests currently need a "posting-ready" seeded CliContext. Seeding is
    done by calling FakeJournalRepo.save() directly (bypassing
    next_journal_number()) rather than assuming any repo-level accessor
    on CliContext, since only service-level accessors are confirmed.
    """
    journal_repo = make_fake_journal_repo()
    posting_repo = make_fake_posting_repo()
    entry = make_journal_entry(journal_number=1)
    await journal_repo.save(entry, created_by=TEST_ACTOR)

    return make_fake_cli_context(
        journal_repo=journal_repo,
        posting_repo=posting_repo,
        chart=_simple_chart(),
    )


@pytest_asyncio.fixture
async def empty_cli_context():
    """CliContext with no journal entries and no postings."""
    return make_fake_cli_context(chart=_simple_chart())


@pytest.mark.unit
class TestPostJournalEntryHandler:
    async def test_returns_posting_view_models(self, journal_cli_context):
        result = await post_journal_entry_handler(journal_cli_context, 1)

        assert len(result) == 2
        assert all(isinstance(vm, PostingViewModel) for vm in result)

    async def test_raises_unknown_journal_entry_for_missing_number(
        self, journal_cli_context
    ):
        with pytest.raises(AppError) as exc_info:
            await post_journal_entry_handler(journal_cli_context, 999)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY

    async def test_raises_journal_already_posted_on_second_post(
        self, journal_cli_context
    ):
        await post_journal_entry_handler(journal_cli_context, 1)

        with pytest.raises(AppError) as exc_info:
            await post_journal_entry_handler(journal_cli_context, 1)

        assert exc_info.value.code == ErrorCode.JOURNAL_ALREADY_POSTED


@pytest.mark.unit
class TestGetPostingsByAccountHandler:
    async def test_returns_postings_after_posting(self, journal_cli_context):
        await post_journal_entry_handler(journal_cli_context, 1)

        result = await get_postings_by_account_handler(journal_cli_context, "Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"

    async def test_matches_case_insensitively(self, journal_cli_context):
        await post_journal_entry_handler(journal_cli_context, 1)

        result = await get_postings_by_account_handler(journal_cli_context, "cash")

        assert len(result) == 1

    async def test_returns_empty_list_when_no_postings_exist(self, empty_cli_context):
        result = await get_postings_by_account_handler(empty_cli_context, "Cash")

        assert result == []


@pytest.mark.unit
class TestGetPostingsByJournalNumberHandler:
    async def test_returns_postings_after_posting(self, journal_cli_context):
        await post_journal_entry_handler(journal_cli_context, 1)

        result = await get_postings_by_journal_number_handler(journal_cli_context, 1)

        assert len(result) == 2
        assert all(vm.journal_number == 1 for vm in result)

    async def test_returns_empty_list_when_journal_number_not_posted(
        self, journal_cli_context
    ):
        result = await get_postings_by_journal_number_handler(journal_cli_context, 1)

        assert result == []

    async def test_returns_empty_list_for_unknown_journal_number(
        self, empty_cli_context
    ):
        result = await get_postings_by_journal_number_handler(empty_cli_context, 999)

        assert result == []


@pytest.mark.unit
class TestPostJournalEntryHandlerAttribution:
    async def test_attributes_the_write_to_the_cli_pre_auth_actor(
        self, simple_chart, create_input
    ):
        posting_repo = FakePostingRepo()
        ctx = CliContext(
            account_repo=make_fake_account_repo(chart=simple_chart),
            journal_repo=FakeJournalRepo(),
            posting_repo=posting_repo,
        )
        journal_service = await ctx.get_journal_service()
        await journal_service.create_journal_entry(create_input, actor=TEST_ACTOR)

        await post_journal_entry_handler(ctx, 1)

        assert posting_repo.saved_created_by == [PRE_AUTH_ACTOR]
