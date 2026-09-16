import pytest
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.account.service import AccountService
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    ValidationAppError,
)

from tests.factories import (
    make_account,
    make_chart_of_accounts,
    make_create_account_input,
    make_fake_account_repo,
    make_update_account_input,
)


@pytest.mark.unit
class TestAccountService:
    async def test_creates_account(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        dto = make_create_account_input()

        result = await service.create_account(dto)

        assert result.code == dto.code
        assert result.name == dto.name
        assert result.category == dto.category
        assert result.normal_balance == "debit"

        assert len(repo.created_accounts) == 1
        assert repo.created_accounts[0].code == dto.code

    async def test_returns_view_model_with_credit_normal_balance(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        dto = make_create_account_input(
            category=AccountCategory.REVENUE,
        )

        result = await service.create_account(dto)

        assert result.category == AccountCategory.REVENUE
        assert result.normal_balance == "credit"

    async def test_raises_when_duplicate_code_exists(self):
        existing = make_account(code="1001")

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        dto = make_create_account_input(
            code="1001",
            name="Petty Cash",
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_account(dto)

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_CODE
        assert exc_info.value.context["field"] == "code"
        assert exc_info.value.context["value"] == "1001"

    async def test_raises_when_duplicate_name_exists(self):
        existing = make_account(
            code="1001",
            name="Cash",
        )

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        dto = make_create_account_input(
            code="2000",
            name="Cash",
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_account(dto)

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert exc_info.value.context["field"] == "name"
        assert exc_info.value.context["value"] == "Cash"

    async def test_raises_validation_error_when_account_name_is_invalid(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        dto = make_create_account_input(
            name="???",
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_account(dto)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert len(exc_info.value.errors) == 1

        violation = exc_info.value.errors[0]

        assert violation.code == ErrorCode.UNKNOWN_ERROR
        assert violation.field == "name"
        assert violation.value == ErrorCode.INVALID_ACCOUNT_NAME

    async def test_updates_account_name(self):
        existing = make_account(
            code="1001",
            name="Cash",
        )

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        dto = make_update_account_input(
            code="1001",
            name="Main Cash",
        )

        result = await service.update_account(dto)

        assert result.code == "1001"
        assert result.name == "Main Cash"
        assert result.category == existing.category

        assert len(repo.updated_accounts) == 1
        assert repo.updated_accounts[0].name == "Main Cash"

    async def test_updates_account_category(self):
        existing = make_account(
            category=AccountCategory.ASSET,
        )

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))
        service = AccountService(repo)

        dto = make_update_account_input(
            code=existing.code,
            category=AccountCategory.REVENUE,
        )

        result = await service.update_account(dto)

        assert result.category == AccountCategory.REVENUE
        assert result.normal_balance == "credit"

    async def test_updates_only_name(self):
        existing = make_account(
            name="Cash",
            category=AccountCategory.ASSET,
        )

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))

        service = AccountService(repo)

        dto = make_update_account_input(
            code=existing.code,
            name="Main Cash",
        )

        result = await service.update_account(dto)

        assert result.name == "Main Cash"
        assert result.category == AccountCategory.ASSET

    async def test_updates_only_category(self):
        existing = make_account(
            name="Cash",
            category=AccountCategory.ASSET,
        )

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))

        service = AccountService(repo)

        dto = make_update_account_input(
            code=existing.code,
            category=AccountCategory.REVENUE,
        )

        result = await service.update_account(dto)

        assert result.name == "Cash"
        assert result.category == AccountCategory.REVENUE

    async def test_allows_update_when_name_is_unchanged(self):
        existing = make_account(
            code="1001",
            name="Cash",
        )

        other = make_account(
            code="2001",
            name="Revenue",
        )

        repo = make_fake_account_repo(
            make_chart_of_accounts(accounts=[existing, other])
        )

        service = AccountService(repo)

        dto = make_update_account_input(
            code="1001",
            name="Cash",
        )

        result = await service.update_account(dto)

        assert result.code == "1001"
        assert result.name == "Cash"

    async def test_raises_when_updating_unknown_account(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        dto = make_update_account_input(code="9999")

        with pytest.raises(AppError) as exc_info:
            await service.update_account(dto)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "9999"

    async def test_raises_when_updated_name_already_exists(self):
        account_one = make_account(
            code="1001",
            name="Cash",
        )

        account_two = make_account(
            code="2001",
            name="Bank",
        )

        repo = make_fake_account_repo(
            make_chart_of_accounts(accounts=[account_one, account_two])
        )

        service = AccountService(repo)

        dto = make_update_account_input(
            code="2001",
            name="Cash",
        )

        with pytest.raises(AppError) as exc_info:
            await service.update_account(dto)

        assert exc_info.value.code == ErrorCode.DUPLICATE_ACCOUNT_NAME
        assert exc_info.value.context["field"] == "name"
        assert exc_info.value.context["value"] == "Cash"

    async def test_raises_validation_error_when_updated_name_is_invalid(self):
        existing = make_account()

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))

        service = AccountService(repo)

        dto = make_update_account_input(
            code=existing.code,
            name="???",
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.update_account(dto)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

        violation = exc_info.value.errors[0]

        assert violation.code == ErrorCode.UNKNOWN_ERROR
        assert violation.field == "name"
        assert violation.value == ErrorCode.INVALID_ACCOUNT_NAME

    async def test_returns_account(self):
        existing = make_account()

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[existing]))

        service = AccountService(repo)

        result = await service.get_account(existing.code)

        assert result.code == existing.code
        assert result.name == existing.name
        assert result.category == existing.category
        assert result.normal_balance == existing.normal_balance

    async def test_raises_when_account_does_not_exist(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        with pytest.raises(AppError) as exc_info:
            await service.get_account("9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "9999"

    async def test_returns_chart_snapshot(self):
        accounts = [
            make_account(code="1001"),
            make_account(code="2001", name="Revenue"),
        ]

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=accounts))

        service = AccountService(repo)

        chart = await service.get_chart()

        assert len(chart.accounts) == 2

    async def test_returns_chart_with_multiple_accounts(self):
        accounts = [
            make_account(code="1001"),
            make_account(code="2001", name="Revenue"),
            make_account(code="3001", name="Equipment"),
        ]

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=accounts))

        service = AccountService(repo)

        chart = await service.get_chart()

        assert len(chart.accounts) == 3

    async def test_resolves_account_by_name(self):
        account = make_account(name="Cash")

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        service = AccountService(repo)

        result = await service.resolve_account("Cash")

        assert result.code == account.code
        assert result.name == account.name
        assert result.category == account.category
        assert result.normal_balance == account.normal_balance

    async def test_resolves_account_case_insensitively(self):
        account = make_account(name="Cash")

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        service = AccountService(repo)

        result = await service.resolve_account("cash")

        assert result.code == account.code

    async def test_raises_when_account_reference_cannot_be_resolved(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        with pytest.raises(AppError) as exc_info:
            await service.resolve_account("Unknown")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "Unknown"

    async def test_returns_empty_account_list(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        result = await service.list_accounts()

        assert result.accounts == []

    async def test_returns_single_account(self):
        account = make_account()

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        service = AccountService(repo)

        result = await service.list_accounts()

        assert len(result.accounts) == 1
        assert result.accounts[0].code == account.code

    async def test_returns_multiple_accounts(self):
        accounts = [
            make_account(code="1001"),
            make_account(code="2001", name="Revenue"),
        ]

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=accounts))

        service = AccountService(repo)

        result = await service.list_accounts()

        assert len(result.accounts) == 2

    async def test_deletes_account(self):
        account = make_account()

        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        service = AccountService(repo)

        await service.delete_account(account.code)

        assert repo.deleted_codes == [account.code]
        assert await repo.get_by_code(account.code) is None

    async def test_raises_when_deleting_unknown_account(self):
        repo = make_fake_account_repo()
        service = AccountService(repo)

        with pytest.raises(AppError) as exc_info:
            await service.delete_account("9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "9999"


@pytest.mark.unit
class TestAccountServiceDeleteWithPostingsCheck:
    async def test_deletes_when_has_postings_check_returns_false(self):
        account = make_account()
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        async def no_postings(name: str) -> bool:
            return False

        service = AccountService(repo, has_postings=no_postings)

        await service.delete_account(account.code)

        assert repo.deleted_codes == [account.code]

    async def test_raises_account_has_postings_when_check_returns_true(self):
        account = make_account()
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        async def has_postings(name: str) -> bool:
            return True

        service = AccountService(repo, has_postings=has_postings)

        with pytest.raises(AppError) as exc_info:
            await service.delete_account(account.code)

        assert exc_info.value.code == ErrorCode.ACCOUNT_HAS_POSTINGS
        assert exc_info.value.context["value"] == account.code

    async def test_does_not_delete_when_postings_exist(self):
        account = make_account()
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))

        async def has_postings(name: str) -> bool:
            return True

        service = AccountService(repo, has_postings=has_postings)

        with pytest.raises(AppError):
            await service.delete_account(account.code)

        assert repo.deleted_codes == []

    async def test_passes_account_name_not_code_to_the_check(self):
        account = make_account(code="1001", name="Cash")
        repo = make_fake_account_repo(make_chart_of_accounts(accounts=[account]))
        received: list[str] = []

        async def recording_check(name: str) -> bool:
            received.append(name)
            return False

        service = AccountService(repo, has_postings=recording_check)

        await service.delete_account(account.code)

        assert received == ["Cash"]

    async def test_still_raises_unknown_account_before_checking_postings(self):
        repo = make_fake_account_repo()
        checked = False

        async def has_postings(name: str) -> bool:
            nonlocal checked
            checked = True
            return True

        service = AccountService(repo, has_postings=has_postings)

        with pytest.raises(AppError) as exc_info:
            await service.delete_account("9999")

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert checked is False
