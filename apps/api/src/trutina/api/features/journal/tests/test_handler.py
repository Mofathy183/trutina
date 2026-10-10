"""Unit tests for the journal feature's handler functions.

Fake-backed via `tests/factories/*`/`tests/fakes/*` -- the same
FakeAccountRepo/FakeJournalRepo the CLI's own handler tests and
JournalService's own unit tests use. Confirms each handler calls
exactly one JournalService method with the right arguments and returns
its result unchanged; JournalService's own business rules are already
covered under core/journal/tests/test_service_unit.py and are not
re-verified here.
"""

import pytest
from trutina.api.features.journal.handler import (
    create_journal_entry,
    get_journal_entry,
    list_journal_entries,
)
from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.journal.dtos import JournalViewModel
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_create_journal_input,
    make_journal_service,
)


def _simple_chart():
    return make_chart_of_accounts(
        accounts=[
            make_account(code="1001", name="Cash", category=AccountCategory.ASSET),
            make_account(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        ]
    )


@pytest.mark.unit
class TestCreateJournalEntryHandler:
    async def test_returns_view_model(self):
        service, _ = make_journal_service(chart=_simple_chart())
        dto = make_create_journal_input()

        result = await create_journal_entry(service, dto)

        assert isinstance(result, JournalViewModel)
        assert result.journal_number == 1

    async def test_propagates_unknown_account_error(self):
        service, _ = make_journal_service()  # no chart seeded
        dto = make_create_journal_input()

        with pytest.raises(AppError) as exc_info:
            await create_journal_entry(service, dto)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.unit
class TestGetJournalEntryHandler:
    async def test_returns_matching_entry(self):
        service, _ = make_journal_service(chart=_simple_chart())
        await create_journal_entry(service, make_create_journal_input())

        result = await get_journal_entry(service, 1)

        assert result.journal_number == 1

    async def test_propagates_unknown_journal_entry_error(self):
        service, _ = make_journal_service(chart=_simple_chart())

        with pytest.raises(AppError) as exc_info:
            await get_journal_entry(service, 999)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY


@pytest.mark.unit
class TestListJournalEntriesHandler:
    async def test_returns_empty_list(self):
        service, _ = make_journal_service(chart=_simple_chart())

        result = await list_journal_entries(service)

        assert result == []

    async def test_returns_all_entries(self):
        service, _ = make_journal_service(chart=_simple_chart())
        await create_journal_entry(service, make_create_journal_input())
        await create_journal_entry(service, make_create_journal_input())

        result = await list_journal_entries(service)

        assert len(result) == 2


@pytest.mark.unit
class TestCreateJournalEntryAttribution:
    async def test_attributes_the_write_to_the_api_pre_auth_actor(
        self, journal_service, create_input
    ):
        service, repo = journal_service

        await create_journal_entry(service, create_input)

        assert repo.saved_created_by == [PRE_AUTH_ACTOR]

    async def test_pre_auth_actor_names_the_api(self):
        assert PRE_AUTH_ACTOR == "system:pre-auth:api"
