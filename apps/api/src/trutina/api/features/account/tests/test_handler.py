"""Unit tests for the account feature's handler functions.

Fake-backed via `tests/factories/*`/`tests/fakes/*` -- the same
FakeAccountRepo the CLI's own handler tests and AccountService's own
unit tests use. Confirms each handler calls exactly one AccountService
method with the right arguments and returns its result unchanged;
AccountService's own business rules are already covered under
core/account/tests/test_service_unit.py and are not re-verified
here.
"""

import pytest
from trutina.api.features.account.handler import (
    create_account,
    delete_account,
    get_account,
    list_accounts,
    update_account,
)
from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.core.account.dtos import AccountViewModel, ChartOfAccountsViewModel
from trutina.core.account.service import AccountService
from trutina.shared.errors import AppError, ErrorCode, ValidationAppError

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_create_account_input,
    make_fake_account_repo,
    make_update_account_input,
)


@pytest.mark.unit
class TestCreateAccountHandler:
    async def test_returns_view_model(self):
        service = AccountService(make_fake_account_repo())
        dto = make_create_account_input(code="1001", name="Cash")

        result = await create_account(service, dto)

        assert isinstance(result, AccountViewModel)
        assert result.code == "1001"

    async def test_propagates_duplicate_code_error(self):
        existing = make_account(code="1001")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)
        dto = make_create_account_input(code="1001", name="Other")

        with pytest.raises(AppError) as exc_info:
            await create_account(service, dto)

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE

    async def test_propagates_validation_error_for_invalid_code(self):
        service = AccountService(make_fake_account_repo())
        dto = make_create_account_input(code="sdgi")

        with pytest.raises(ValidationAppError) as exc_info:
            await create_account(service, dto)

        assert exc_info.value.errors[0].value == ErrorCode.INVALID_ACCOUNT_CODE


@pytest.mark.unit
class TestUpdateAccountHandler:
    async def test_returns_updated_view_model(self):
        existing = make_account(code="1001", name="Cash")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)
        dto = make_update_account_input(code="1001", name="Main Cash")

        result = await update_account(service, dto)

        assert result.name == "Main Cash"

    async def test_propagates_unknown_account_error(self):
        service = AccountService(make_fake_account_repo())
        dto = make_update_account_input(code="9999")

        with pytest.raises(AppError) as exc_info:
            await update_account(service, dto)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.unit
class TestGetAccountHandler:
    async def test_returns_matching_account(self):
        existing = make_account(code="1001", name="Cash")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        result = await get_account(service, "1001")

        assert result.code == "1001"

    async def test_propagates_unknown_account_error(self):
        service = AccountService(make_fake_account_repo())

        with pytest.raises(AppError) as exc_info:
            await get_account(service, "9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.unit
class TestListAccountsHandler:
    async def test_returns_empty_chart(self):
        service = AccountService(make_fake_account_repo())

        result = await list_accounts(service)

        assert isinstance(result, ChartOfAccountsViewModel)
        assert result.accounts == []

    async def test_returns_all_accounts(self):
        accounts = [
            make_account(code="1001"),
            make_account(code="2001", name="Revenue"),
        ]
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=accounts))
        service = AccountService(repo)

        result = await list_accounts(service)

        assert len(result.accounts) == 2


@pytest.mark.unit
class TestDeleteAccountHandler:
    async def test_deletes_account(self):
        existing = make_account(code="1001")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        await delete_account(service, "1001")

        assert repo.deleted_codes == ["1001"]

    async def test_propagates_unknown_account_error(self):
        service = AccountService(make_fake_account_repo())

        with pytest.raises(AppError) as exc_info:
            await delete_account(service, "9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT


@pytest.mark.unit
class TestAccountWriteHandlersPassPreAuthActor:
    async def test_create_passes_pre_auth_actor(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        await create_account(
            service, make_create_account_input(code="1001", name="Cash")
        )

        assert repo.created_by_on_create == [PRE_AUTH_ACTOR]

    async def test_update_passes_pre_auth_actor(self):
        existing = make_account(code="1001", name="Cash")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        await update_account(
            service, make_update_account_input(code="1001", name="Main Cash")
        )

        assert repo.created_by_on_update == [PRE_AUTH_ACTOR]

    async def test_delete_passes_pre_auth_actor(self):
        existing = make_account(code="1001")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        await delete_account(service, "1001")

        assert repo.created_by_on_delete == [PRE_AUTH_ACTOR]
