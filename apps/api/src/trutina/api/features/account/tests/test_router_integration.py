"""Integration tests for the account router.

One happy path + one conflict path per route is enough here -- the
unit tier (test_router_unit.py) already walks every validation branch.
Seeds through the real endpoints rather than a repo fixture, per
`Trutina API Feature & Testing Prompt` Section 5's seeding pattern, so
each test also implicitly proves the endpoint it depends on for setup.
"""

import pytest
from trutina.shared.errors import ErrorCode

from tests.factories import make_create_account_request, make_update_account_request


@pytest.mark.integration
class TestCreateAccountRouteIntegration:
    async def test_creates_and_persists_account(self, real_api_client):
        response = await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )

        assert response.status_code == 201
        assert response.json()["account"]["code"] == "1001"

    async def test_returns_409_on_duplicate_code_against_real_index(
        self, real_api_client
    ):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )

        response = await real_api_client.post(
            "/accounts",
            json=make_create_account_request(code="1001", name="Petty Cash"),
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.DUPLICATE_ACCOUNT_CODE.value


@pytest.mark.integration
class TestListAccountsRouteIntegration:
    async def test_returns_persisted_accounts(self, real_api_client):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="2001", name="Revenue")
        )

        response = await real_api_client.get("/accounts")

        codes = [a["code"] for a in response.json()["accounts"]]
        assert codes == ["1001", "2001"]


@pytest.mark.integration
class TestGetAccountRouteIntegration:
    async def test_returns_existing_account(self, real_api_client):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )

        response = await real_api_client.get("/accounts/1001")

        assert response.status_code == 200
        assert response.json()["account"]["name"] == "Cash"

    async def test_returns_404_for_unknown_account(self, real_api_client):
        response = await real_api_client.get("/accounts/9999")

        assert response.status_code == 404


@pytest.mark.integration
class TestUpdateAccountRouteIntegration:
    async def test_updates_and_persists_name(self, real_api_client):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )

        await real_api_client.patch(
            "/accounts/1001", json=make_update_account_request(name="Main Cash")
        )
        refetched = await real_api_client.get("/accounts/1001")

        assert refetched.json()["account"]["name"] == "Main Cash"

    async def test_returns_409_on_rename_to_existing_name(self, real_api_client):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="2001", name="Bank")
        )

        response = await real_api_client.patch(
            "/accounts/2001", json=make_update_account_request(name="Cash")
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.DUPLICATE_ACCOUNT_NAME.value


@pytest.mark.integration
class TestDeleteAccountRouteIntegration:
    async def test_deletes_and_persists_removal(self, real_api_client):
        await real_api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )

        delete_response = await real_api_client.delete("/accounts/1001")
        refetched = await real_api_client.get("/accounts/1001")

        assert delete_response.status_code == 200
        assert refetched.status_code == 404

    async def test_returns_404_for_unknown_account(self, real_api_client):
        response = await real_api_client.delete("/accounts/9999")

        assert response.status_code == 404
