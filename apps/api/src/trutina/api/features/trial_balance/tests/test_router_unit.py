"""Unit tests for the trial-balance router, against fake_container + api_client.

fake_container's default trial_balance_service is wired to an empty
FakeTrialBalanceRepo with no aggregation link back to whatever gets
posted through posting_service in the same test -- FakeTrialBalanceRepo
only ever returns the rows it was seeded with at construction (see
tests/fakes/trial_balance_repo.py's own docstring). Tests that need
populated entries therefore override get_trial_balance_service directly
via override_service() with a TrialBalanceService built from a
pre-seeded fake, mirroring test_router_unit.py's own override pattern
for a single service without faking the whole Container.
"""

import pytest
from trutina.api.composition.dependencies import get_trial_balance_service

from tests.factories import make_account_balance_entry, make_trial_balance_service


@pytest.mark.unit
class TestGetTrialBalanceRoute:
    async def test_returns_200_with_empty_entries_by_default(self, api_client):
        response = await api_client.get("/trial-balance")

        body = response.json()
        assert response.status_code == 200
        assert body["entries"] == []
        assert body["is_balanced"] is True

    async def test_returns_populated_entries(
        self, api_app, api_client, override_service
    ):
        service, _repo = make_trial_balance_service(
            entries=[
                make_account_balance_entry(account="Cash"),
                make_account_balance_entry(account="Sales Revenue"),
            ]
        )
        override_service(api_app, get_trial_balance_service, service)

        response = await api_client.get("/trial-balance")

        body = response.json()
        assert response.status_code == 200
        assert len(body["entries"]) == 2

    async def test_accepts_as_of_query_param(self, api_client):
        response = await api_client.get(
            "/trial-balance", params={"as_of": "2025-01-01T00:00:00"}
        )

        assert response.status_code == 200

    async def test_rejects_invalid_as_of_query_param(self, api_client):
        response = await api_client.get(
            "/trial-balance", params={"as_of": "not-a-date"}
        )

        assert response.status_code == 422

    async def test_response_success_flag_is_true(self, api_client):
        response = await api_client.get("/trial-balance")

        assert response.json()["success"] is True

    async def test_response_carries_computed_totals(
        self, api_app, api_client, override_service
    ):
        from decimal import Decimal

        service, _repo = make_trial_balance_service(
            entries=[
                make_account_balance_entry(
                    account="Cash",
                    debit_total=Decimal("100"),
                    credit_total=Decimal("0"),
                ),
                make_account_balance_entry(
                    account="Sales Revenue",
                    debit_total=Decimal("0"),
                    credit_total=Decimal("100"),
                ),
            ]
        )
        override_service(api_app, get_trial_balance_service, service)

        response = await api_client.get("/trial-balance")

        body = response.json()
        assert Decimal(body["total_debits"]) == Decimal("100")
        assert Decimal(body["total_credits"]) == Decimal("100")
        assert body["is_balanced"] is True
