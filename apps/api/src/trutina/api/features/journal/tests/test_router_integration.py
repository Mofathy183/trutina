"""Integration tests for the journal router.

One happy path + one conflict/error path per route is enough here --
the unit tier (test_router_unit.py) already walks every validation
branch. Seeds through the real /accounts and /journal-entries endpoints
rather than a repo fixture, per `Trutina API Feature & Testing Prompt`
Section 5's seeding pattern.
"""

import pytest
from trutina.shared.errors import ErrorCode

from tests.factories import (
    make_create_account_request,
    make_create_journal_entry_request,
)


async def _seed_accounts(real_api_client):
    await real_api_client.post(
        "/accounts", json=make_create_account_request(code="1001", name="Cash")
    )
    await real_api_client.post(
        "/accounts",
        json=make_create_account_request(
            code="4001", name="Sales Revenue", category="REVENUE"
        ),
    )


@pytest.mark.integration
class TestCreateJournalEntryRouteIntegration:
    async def test_creates_and_persists_entry(self, real_api_client):
        await _seed_accounts(real_api_client)

        response = await real_api_client.post(
            "/journal-entries", json=make_create_journal_entry_request()
        )

        assert response.status_code == 201
        assert response.json()["entry"]["journal_number"] == 1

    async def test_returns_404_when_account_unknown(self, real_api_client):
        response = await real_api_client.post(
            "/journal-entries", json=make_create_journal_entry_request()
        )

        assert response.status_code == 404
        assert response.json()["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value


@pytest.mark.integration
class TestListJournalEntriesRouteIntegration:
    async def test_returns_persisted_entries(self, real_api_client):
        await _seed_accounts(real_api_client)
        await real_api_client.post(
            "/journal-entries", json=make_create_journal_entry_request()
        )
        await real_api_client.post(
            "/journal-entries", json=make_create_journal_entry_request()
        )

        response = await real_api_client.get("/journal-entries")

        numbers = [e["journal_number"] for e in response.json()["entries"]]
        assert numbers == [1, 2]


@pytest.mark.integration
class TestGetJournalEntryRouteIntegration:
    async def test_returns_existing_entry(self, real_api_client):
        await _seed_accounts(real_api_client)
        await real_api_client.post(
            "/journal-entries", json=make_create_journal_entry_request()
        )

        response = await real_api_client.get("/journal-entries/1")

        assert response.status_code == 200
        assert response.json()["entry"]["journal_number"] == 1

    async def test_returns_404_for_unknown_journal_number(self, real_api_client):
        response = await real_api_client.get("/journal-entries/999")

        assert response.status_code == 404
