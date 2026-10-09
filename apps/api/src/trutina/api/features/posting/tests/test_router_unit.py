"""Unit tests for the posting router, against fake_container + api_client.

No route exists yet to create accounts or journal entries over HTTP
(only the system feature is mounted besides this one), so seeding for
the "post an entry" tests goes directly through
fake_container.account_service / .journal_service -- the same
fake-backed services api_client's requests are ultimately routed to --
rather than through a real endpoint. This mirrors
test_container_services_are_usable_during_lifespan's pattern of using
the container's services directly, just at the unit tier instead of
integration.
"""

import pytest
from trutina.core.account.schemas.account import AccountCategory

from tests.factories import (
    TEST_ACTOR,
    make_create_account_input,
    make_create_journal_input,
)


async def _seed_accounts(fake_container):
    await fake_container.account_service.create_account(
        make_create_account_input(code="1001", name="Cash")
    )
    await fake_container.account_service.create_account(
        make_create_account_input(
            code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
        )
    )


@pytest.mark.unit
class TestPostJournalEntryRoute:
    async def test_returns_201(self, api_client, fake_container):
        await _seed_accounts(fake_container)
        entry = await fake_container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        response = await api_client.post(f"/postings/{entry.journal_number}")

        assert response.status_code == 201

    async def test_returns_one_posting_per_line(self, api_client, fake_container):
        await _seed_accounts(fake_container)
        entry = await fake_container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        response = await api_client.post(f"/postings/{entry.journal_number}")

        body = response.json()
        assert len(body["postings"]) == 2

    async def test_returns_404_for_unknown_journal_number(self, api_client):
        response = await api_client.post("/postings/999")

        assert response.status_code == 404

    async def test_returns_409_when_already_posted(self, api_client, fake_container):
        await _seed_accounts(fake_container)
        entry = await fake_container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await api_client.post(f"/postings/{entry.journal_number}")

        response = await api_client.post(f"/postings/{entry.journal_number}")

        assert response.status_code == 409

    async def test_rejects_non_positive_journal_number(self, api_client):
        response = await api_client.post("/postings/0")

        assert response.status_code == 422


@pytest.mark.unit
class TestGetPostingsByAccountRoute:
    async def test_returns_200_with_empty_list_when_none_exist(self, api_client):
        response = await api_client.get("/postings/by-account/Cash")

        assert response.status_code == 200
        assert response.json()["postings"] == []

    async def test_returns_postings_for_account(self, api_client, fake_container):
        await _seed_accounts(fake_container)
        entry = await fake_container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await api_client.post(f"/postings/{entry.journal_number}")

        response = await api_client.get("/postings/by-account/Cash")

        body = response.json()
        assert len(body["postings"]) == 1
        assert body["postings"][0]["account"] == "Cash"

    async def test_rejects_account_shorter_than_two_characters(self, api_client):
        response = await api_client.get("/postings/by-account/C")

        assert response.status_code == 422


@pytest.mark.unit
class TestGetPostingsByJournalNumberRoute:
    async def test_returns_200_with_empty_list_when_none_exist(self, api_client):
        response = await api_client.get("/postings/by-journal/999")

        assert response.status_code == 200
        assert response.json()["postings"] == []

    async def test_returns_postings_for_journal_number(
        self, api_client, fake_container
    ):
        await _seed_accounts(fake_container)
        entry = await fake_container.journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )
        await api_client.post(f"/postings/{entry.journal_number}")

        response = await api_client.get(f"/postings/by-journal/{entry.journal_number}")

        body = response.json()
        assert len(body["postings"]) == 2

    async def test_rejects_non_positive_journal_number(self, api_client):
        response = await api_client.get("/postings/by-journal/0")

        assert response.status_code == 422
