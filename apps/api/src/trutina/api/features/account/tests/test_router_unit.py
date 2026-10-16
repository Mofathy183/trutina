"""Unit tests for the account router: full Mapper -> Handler -> Presenter
chain, driven over real HTTP via `api_client` + `fake_container`.

Does NOT re-verify AccountService business rules (core/account/tests/),
mapper/presenter field-mapping in isolation (test_mapper.py,
test_presenter.py), or handler call-shape (test_handler.py). This tier
proves the wiring holds end-to-end and that errors surface as the
correct HTTP status/envelope via the registered exception handlers.
"""

import pytest
from trutina.api.composition.dependencies import get_account_service
from trutina.core.account.schemas.account import AccountCategory
from trutina.shared.errors import ErrorCode

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_create_account_request,
    make_fake_account_repo,
    make_update_account_request,
)


@pytest.mark.unit
class TestCreateAccountRoute:
    async def test_returns_201(self, api_client):
        response = await api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )

        assert response.status_code == 201

    async def test_returns_created_account_in_envelope(self, api_client):
        response = await api_client.post(
            "/accounts",
            json=make_create_account_request(
                code="1001", name="Cash", category=AccountCategory.ASSET.value
            ),
        )

        body = response.json()
        assert body["success"] is True
        assert body["account"]["code"] == "1001"
        assert body["account"]["name"] == "Cash"
        assert body["account"]["normal_balance"] == "debit"

    async def test_returns_409_on_duplicate_code(
        self, api_app, api_client, override_service
    ):
        existing = make_account(code="1001")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        from trutina.core.account.service import AccountService

        override_service(api_app, get_account_service, AccountService(repo))

        response = await api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Other")
        )

        assert response.status_code == 409
        assert response.json()["error_code"] == ErrorCode.DUPLICATE_ACCOUNT_CODE.value

    async def test_returns_422_on_missing_required_field(self, api_client):
        response = await api_client.post("/accounts", json={"code": "1001"})

        assert response.status_code == 422

    async def test_returns_422_on_invalid_account_name(self, api_client):
        response = await api_client.post(
            "/accounts",
            json=make_create_account_request(code="1001", name="???"),
        )

        assert response.status_code == 422

    async def test_returns_422_on_invalid_account_code(self, api_client):
        response = await api_client.post(
            "/accounts",
            json=make_create_account_request(code="sdgi"),
        )

        body = response.json()
        assert response.status_code == 422
        assert body["success"] is False
        assert body["error_code"] == ErrorCode.VALIDATION_ERROR.value
        assert body["details"][0]["code"] == ErrorCode.INVALID_ACCOUNT_CODE.value
        assert body["details"][0]["field"] == "code"
        assert body["details"][0]["message"] == "The account code is not valid."
        assert body["details"][0]["hint"] == (
            "Account codes must be 4 to 6 digits (0-9), for example '1001'."
        )


@pytest.mark.unit
class TestListAccountsRoute:
    async def test_returns_200(self, api_client):
        response = await api_client.get("/accounts")

        assert response.status_code == 200

    async def test_returns_empty_list_when_no_accounts(self, api_client):
        response = await api_client.get("/accounts")

        assert response.json()["accounts"] == []

    async def test_returns_created_accounts(self, api_client):
        await api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )
        await api_client.post(
            "/accounts",
            json=make_create_account_request(code="2001", name="Revenue"),
        )

        response = await api_client.get("/accounts")

        codes = [a["code"] for a in response.json()["accounts"]]
        assert codes == ["1001", "2001"]


@pytest.mark.unit
class TestGetAccountRoute:
    async def test_returns_200_for_existing_account(self, api_client):
        await api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )

        response = await api_client.get("/accounts/1001")

        assert response.status_code == 200
        assert response.json()["account"]["code"] == "1001"

    async def test_returns_404_for_unknown_account(self, api_client):
        response = await api_client.get("/accounts/9999")

        assert response.status_code == 404
        body = response.json()
        assert body["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value
        assert "9999" in body["message"]


@pytest.mark.unit
class TestUpdateAccountRoute:
    async def test_returns_200_and_updated_name(self, api_client):
        await api_client.post(
            "/accounts", json=make_create_account_request(code="1001", name="Cash")
        )

        response = await api_client.patch(
            "/accounts/1001", json=make_update_account_request(name="Main Cash")
        )

        assert response.status_code == 200
        assert response.json()["account"]["name"] == "Main Cash"

    async def test_returns_404_for_unknown_account(self, api_client):
        response = await api_client.patch(
            "/accounts/9999", json=make_update_account_request(name="Ghost")
        )

        assert response.status_code == 404
        assert response.json()["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value

    async def test_omitted_fields_leave_existing_values(self, api_client):
        await api_client.post(
            "/accounts",
            json=make_create_account_request(
                code="1001", name="Cash", category=AccountCategory.ASSET.value
            ),
        )

        response = await api_client.patch("/accounts/1001", json={})

        body = response.json()["account"]
        assert body["name"] == "Cash"
        assert body["category"] == AccountCategory.ASSET.value


@pytest.mark.unit
class TestDeleteAccountRoute:
    async def test_returns_200_and_echoes_code(self, api_client):
        await api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )

        response = await api_client.delete("/accounts/1001")

        assert response.status_code == 200
        assert response.json()["code"] == "1001"

    async def test_account_no_longer_retrievable_after_delete(self, api_client):
        await api_client.post(
            "/accounts", json=make_create_account_request(code="1001")
        )
        await api_client.delete("/accounts/1001")

        response = await api_client.get("/accounts/1001")

        assert response.status_code == 404

    async def test_returns_404_for_unknown_account(self, api_client):
        response = await api_client.delete("/accounts/9999")

        assert response.status_code == 404
        assert response.json()["error_code"] == ErrorCode.UNKNOWN_ACCOUNT.value
