"""Integration tests for the trial-balance router against real PostgreSQL.

Seeds through real_api_app.state.container's real, Postgres-backed
account_service/journal_service/posting_service directly -- there is
still no account or journal-entry HTTP route mounted anywhere in this
API to create data through the real endpoint, mirroring the same
deviation posting's own test_router_integration.py documents.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.account.schemas.account import AccountCategory

from tests.factories import make_create_account_input, make_create_journal_input


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
class TestGetTrialBalanceRouteIntegration:
    async def test_returns_empty_report_on_fresh_database(
        self, real_api_client, real_api_app
    ):
        response = await real_api_client.get("/trial-balance")

        body = response.json()
        assert response.status_code == 200
        assert body["entries"] == []
        assert body["is_balanced"] is True

    async def test_reflects_a_posted_journal_entry(self, real_api_client, real_api_app):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input()
        )
        await real_api_app.state.container.posting_service.post_journal_entry(
            entry.journal_number
        )

        response = await real_api_client.get("/trial-balance")

        body = response.json()
        by_account = {e["account"]: e for e in body["entries"]}
        assert response.status_code == 200
        assert Decimal(by_account["Cash"]["debit_total"]) == Decimal("100.00")
        assert Decimal(by_account["Sales Revenue"]["credit_total"]) == Decimal("100.00")
        assert body["is_balanced"] is True

    async def test_respects_as_of_query_param(self, real_api_client, real_api_app):
        await _seed_accounts(real_api_app)
        entry = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 6, 1))
        )
        await real_api_app.state.container.posting_service.post_journal_entry(
            entry.journal_number
        )

        response = await real_api_client.get(
            "/trial-balance", params={"as_of": "2025-01-01T00:00:00"}
        )

        assert response.status_code == 200
        assert response.json()["entries"] == []

    async def test_all_time_report_includes_every_posting(
        self, real_api_client, real_api_app
    ):
        await _seed_accounts(real_api_app)
        early = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 1, 1))
        )
        late = await real_api_app.state.container.journal_service.create_journal_entry(
            make_create_journal_input(posting_date=datetime(2025, 6, 1))
        )
        await real_api_app.state.container.posting_service.post_journal_entry(
            early.journal_number
        )
        await real_api_app.state.container.posting_service.post_journal_entry(
            late.journal_number
        )

        response = await real_api_client.get("/trial-balance")

        body = response.json()
        by_account = {e["account"]: e for e in body["entries"]}
        assert Decimal(by_account["Cash"]["debit_total"]) == Decimal("200.00")
