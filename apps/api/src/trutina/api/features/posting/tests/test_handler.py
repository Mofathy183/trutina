import pytest
from trutina.api.features.posting.handler import (
    get_postings_by_account_handler,
    get_postings_by_journal_number_handler,
    post_journal_entry_handler,
)
from trutina.core.posting.dtos import PostingViewModel
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    TEST_ACTOR,
    make_create_journal_input,
    make_posting_feature_chart,
    make_posting_service,
)


@pytest.mark.unit
class TestPostJournalEntryHandler:
    async def test_returns_posting_view_models(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )
        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        result = await post_journal_entry_handler(posting_service, entry.journal_number)

        assert len(result) == 2
        assert all(isinstance(vm, PostingViewModel) for vm in result)

    async def test_calls_underlying_service_with_given_journal_number(self):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=make_posting_feature_chart()
        )
        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        await post_journal_entry_handler(posting_service, entry.journal_number)

        assert len(posting_repo.saved_batches) == 1

    async def test_raises_app_error_for_unknown_journal_number(self):
        posting_service, _journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )

        with pytest.raises(AppError) as exc_info:
            await post_journal_entry_handler(posting_service, 999)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY

    async def test_raises_app_error_when_already_posted(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )
        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await post_journal_entry_handler(posting_service, entry.journal_number)

        with pytest.raises(AppError) as exc_info:
            await post_journal_entry_handler(posting_service, entry.journal_number)

        assert exc_info.value.code == ErrorCode.JOURNAL_ALREADY_POSTED


@pytest.mark.unit
class TestGetPostingsByAccountHandler:
    async def test_returns_empty_list_when_no_postings_exist(self):
        posting_service, _journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )

        result = await get_postings_by_account_handler(posting_service, "Cash")

        assert result == []

    async def test_returns_postings_for_account(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )
        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await post_journal_entry_handler(posting_service, entry.journal_number)

        result = await get_postings_by_account_handler(posting_service, "Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"


@pytest.mark.unit
class TestGetPostingsByJournalNumberHandler:
    async def test_returns_empty_list_when_no_postings_exist(self):
        posting_service, _journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )

        result = await get_postings_by_journal_number_handler(posting_service, 999)

        assert result == []

    async def test_returns_postings_for_journal_number(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=make_posting_feature_chart()
        )
        entry = await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await post_journal_entry_handler(posting_service, entry.journal_number)

        result = await get_postings_by_journal_number_handler(
            posting_service, entry.journal_number
        )

        assert len(result) == 2
        assert all(vm.journal_number == entry.journal_number for vm in result)
