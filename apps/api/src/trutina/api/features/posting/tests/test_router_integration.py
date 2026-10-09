"""Integration tests for the posting router against real MongoDB.

DEVIATION FROM STANDARD GUIDANCE: the testing prompt's usual pattern is
to seed integration tests "through the real endpoint, not a repo
shortcut." That isn't possible here -- there is no account or
journal-entry HTTP route mounted anywhere in this API yet (only
`system` and this `posting` feature exist), so a journal entry cannot
be created over HTTP at all. Seeding therefore goes through
real_api_app.state.container's real, Mongo-backed account_service and
journal_service directly -- the same services the HTTP routes under
test ultimately call -- rather than bypassing the stack entirely with
a raw repo. Once account/journal-entry routes exist, this seeding
should switch to real HTTP calls per the standard pattern.
"""

import pytest
from trutina.core.account.schemas.account import AccountCategory

from tests.factories import (
    TEST_ACTOR,
    make_create_account_input,
    make_create_journal_input,
)


async def _seed_accounts(app):
    await app.state.container.account_service.create_account(
        make_create_account_input(code="1001", name="Cash")
    )
    await app.state.container.account_service.create_account(
        make_create_account_input(
            code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
        )
    )


@pytest.mark.integration
class TestPostJournalEntryRoute:
    async def test_posts_journal_entry_and_returns_postings(
        self, real_api_client, real_api_app
    ):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        response = await real_api_client.post(f"/postings/{entry.journal_number}")

        assert response.status_code == 201
        assert len(response.json()["postings"]) == 2

    async def test_conflict_path_returns_409_on_second_post(
        self, real_api_client, real_api_app
    ):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await real_api_client.post(f"/postings/{entry.journal_number}")

        response = await real_api_client.post(f"/postings/{entry.journal_number}")

        assert response.status_code == 409


@pytest.mark.integration
class TestGetPostingsByAccountRoute:
    async def test_returns_postings_persisted_via_real_mongo(
        self, real_api_client, real_api_app
    ):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await real_api_client.post(f"/postings/{entry.journal_number}")

        response = await real_api_client.get("/postings/by-account/Cash")

        body = response.json()
        assert response.status_code == 200
        assert len(body["postings"]) == 1
        assert body["postings"][0]["account"] == "Cash"


@pytest.mark.integration
class TestGetPostingsByJournalNumberRoute:
    async def test_returns_postings_persisted_via_real_mongo(
        self, real_api_client, real_api_app
    ):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await real_api_client.post(f"/postings/{entry.journal_number}")

        response = await real_api_client.get(
            f"/postings/by-journal/{entry.journal_number}"
        )

        assert response.status_code == 200
        assert len(response.json()["postings"]) == 2
