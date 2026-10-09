import logging
from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.journal.dtos import (
    JournalLineInput,
    JournalLineViewModel,
    JournalViewModel,
)
from trutina.core.journal.schemas.journal import JournalEntry
from trutina.shared.errors import (
    AppError,
    ErrorCode,
    FieldViolation,
    ValidationAppError,
)

from tests.factories import (
    TEST_ACTOR,
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
class TestJournalServiceCreate:
    async def test_returns_journal_view_model(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert isinstance(result, JournalViewModel)

    async def test_assigns_journal_number_from_repo(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.journal_number == 1

    async def test_sequential_numbers_on_multiple_creates(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        first = await service.create_journal_entry(input_, actor=TEST_ACTOR)
        second = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert first.journal_number == 1
        assert second.journal_number == 2

    async def test_persists_entry_to_repo(self):
        service, repo = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(repo.saved_entries) == 1
        assert isinstance(repo.saved_entries[0], JournalEntry)

    async def test_saved_entry_matches_returned_view_model(self):
        service, repo = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        saved = repo.saved_entries[0]
        assert saved.journal_number == result.journal_number
        assert saved.posting_date == result.posting_date

    async def test_saved_entry_contains_expected_lines(self):
        service, repo = make_journal_service(chart=_simple_chart())

        input_ = make_create_journal_input()

        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        saved = repo.saved_entries[0]

        assert len(saved.lines) == 2

        assert saved.lines[0].account == "Cash"
        assert saved.lines[0].debit_amount == Decimal("100")
        assert saved.lines[0].credit_amount == Decimal("0")

        assert saved.lines[1].account == "Sales Revenue"
        assert saved.lines[1].debit_amount == Decimal("0")
        assert saved.lines[1].credit_amount == Decimal("100")

    async def test_view_model_carries_correct_totals(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("250.00")),
                JournalLineInput(
                    account="Sales Revenue", credit_amount=Decimal("250.00")
                ),
            ]
        )

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.total_debits == Decimal("250.00")
        assert result.total_credits == Decimal("250.00")
        assert result.is_balanced is True

    async def test_view_model_lines_match_input_accounts(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(result.lines) == 2

        first = result.lines[0]
        second = result.lines[1]

        assert isinstance(first, JournalLineViewModel)
        assert isinstance(second, JournalLineViewModel)

        assert first.account == "Cash"
        assert first.debit_amount == Decimal("100")
        assert first.credit_amount == Decimal("0")

        assert second.account == "Sales Revenue"
        assert second.debit_amount == Decimal("0")
        assert second.credit_amount == Decimal("100")

    async def test_description_propagated_to_view_model(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(description="Opening balance")

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.description == "Opening balance"

    async def test_none_description_propagated_to_view_model(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(description=None)

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.description is None

    async def test_posting_date_propagated_to_view_model(self):
        service, _ = make_journal_service(chart=_simple_chart())
        posting_date = datetime(2024, 6, 15)
        input_ = make_create_journal_input(posting_date=posting_date)

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.posting_date == posting_date


@pytest.mark.unit
class TestJournalServiceCreateAccountValidation:
    async def test_raises_app_error_for_unknown_debit_account(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(
                    account="Nonexistent Account", debit_amount=Decimal("100")
                ),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT

    async def test_raises_app_error_for_unknown_credit_account(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("100")),
                JournalLineInput(account="Ghost Account", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT

    async def test_error_context_carries_unresolved_account_name(self):
        service, _ = make_journal_service(chart=_simple_chart())
        bad_name = "Nonexistent Account"
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account=bad_name, debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert exc_info.value.context["identifier"] == bad_name
        assert exc_info.value.context["resource"] == "account"

    async def test_repo_not_called_when_account_validation_fails(self):
        service, repo = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(
                    account="Nonexistent Account", debit_amount=Decimal("100")
                ),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(AppError):
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(repo.saved_entries) == 0

    async def test_resolves_account_case_insensitively(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="cash", debit_amount=Decimal("100")),
                JournalLineInput(account="SALES REVENUE", credit_amount=Decimal("100")),
            ]
        )

        result = await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert result.journal_number == 1

    async def test_reports_first_unknown_account(self):
        service, _ = make_journal_service(chart=_simple_chart())

        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(
                    account="Missing One",
                    debit_amount=Decimal("100"),
                ),
                JournalLineInput(
                    account="Missing Two",
                    credit_amount=Decimal("100"),
                ),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ACCOUNT
        assert exc_info.value.context["identifier"] == "Missing One"


@pytest.mark.unit
class TestJournalServiceCreateDomainValidation:
    async def test_raises_validation_app_error_for_unbalanced_entry(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("99")),
            ]
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR

        assert any(
            v.code == ErrorCode.UNKNOWN_ERROR and v.value == ErrorCode.UNBALANCED_ENTRY
            for v in error.errors
        )

    async def test_raises_validation_app_error_for_future_posting_date(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(posting_date=datetime(2099, 1, 1))

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert any(
            v.code == ErrorCode.UNKNOWN_ERROR and v.value == ErrorCode.FUTURE_DATE
            for v in error.errors
        )

    async def test_raises_validation_app_error_for_line_with_both_debit_and_credit(
        self,
    ):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(
                    account="Cash",
                    debit_amount=Decimal("100"),
                    credit_amount=Decimal("100"),
                ),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(exc_info.value.errors) > 0
        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

    async def test_validation_app_error_has_non_empty_errors_list(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("50")),
            ]
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(exc_info.value.errors) > 0

    async def test_repo_not_called_when_domain_validation_fails(self):
        service, repo = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("999")),
            ]
        )

        with pytest.raises(ValidationAppError):
            await service.create_journal_entry(input_, actor=TEST_ACTOR)

        assert len(repo.saved_entries) == 0


@pytest.mark.unit
class TestJournalServiceGet:
    async def test_returns_view_model_for_existing_entry(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.get_journal_entry(1)

        assert isinstance(result, JournalViewModel)
        assert result.journal_number == 1

    async def test_returned_view_model_matches_created_entry(self):
        service, _ = make_journal_service(chart=_simple_chart())
        posting_date = datetime(2024, 3, 10)
        input_ = make_create_journal_input(
            posting_date=posting_date, description="Payroll"
        )
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.get_journal_entry(1)

        assert result.posting_date == posting_date
        assert result.description == "Payroll"

    async def test_raises_app_error_for_unknown_journal_number(self):
        service, _ = make_journal_service(chart=_simple_chart())

        with pytest.raises(AppError) as exc_info:
            await service.get_journal_entry(999)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY

    async def test_error_context_carries_journal_number(self):
        service, _ = make_journal_service(chart=_simple_chart())

        with pytest.raises(AppError) as exc_info:
            await service.get_journal_entry(42)

        assert exc_info.value.context["identifier"] == "42"
        assert exc_info.value.context["resource"] == "journal_entry"

    async def test_returns_totals_from_persisted_entry(self):
        service, _ = make_journal_service(chart=_simple_chart())

        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(
                    account="Cash",
                    debit_amount=Decimal("250"),
                ),
                JournalLineInput(
                    account="Sales Revenue",
                    credit_amount=Decimal("250"),
                ),
            ]
        )

        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.get_journal_entry(1)

        assert result.total_debits == Decimal("250")
        assert result.total_credits == Decimal("250")
        assert result.is_balanced is True


@pytest.mark.unit
class TestJournalServiceList:
    async def test_returns_empty_list_when_no_entries_exist(self):
        service, _ = make_journal_service(chart=_simple_chart())

        result = await service.list_journal_entries()

        assert result == []

    async def test_returns_single_entry_after_one_create(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.list_journal_entries()

        assert len(result) == 1
        assert isinstance(result[0], JournalViewModel)

    async def test_returns_all_entries_after_multiple_creates(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()
        await service.create_journal_entry(input_, actor=TEST_ACTOR)
        await service.create_journal_entry(input_, actor=TEST_ACTOR)
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.list_journal_entries()

        assert len(result) == 3

    async def test_entries_ordered_ascending_by_journal_number(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()
        await service.create_journal_entry(input_, actor=TEST_ACTOR)
        await service.create_journal_entry(input_, actor=TEST_ACTOR)
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.list_journal_entries()

        numbers = [vm.journal_number for vm in result]

        assert numbers == [1, 2, 3]

    async def test_list_returns_view_models_not_domain_objects(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input()
        await service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await service.list_journal_entries()

        assert all(isinstance(vm, JournalViewModel) for vm in result)

    async def test_list_preserves_entry_descriptions(self):
        service, _ = make_journal_service(chart=_simple_chart())

        await service.create_journal_entry(
            make_create_journal_input(description="Opening"), actor=TEST_ACTOR
        )

        await service.create_journal_entry(
            make_create_journal_input(description="Payroll"), actor=TEST_ACTOR
        )

        result = await service.list_journal_entries()

        assert result[0].description == "Opening"
        assert result[1].description == "Payroll"

    async def test_list_preserves_entry_totals(self):
        service, _ = make_journal_service(chart=_simple_chart())

        await service.create_journal_entry(
            make_create_journal_input(
                lines=[
                    JournalLineInput(
                        account="Cash",
                        debit_amount=Decimal("500"),
                    ),
                    JournalLineInput(
                        account="Sales Revenue",
                        credit_amount=Decimal("500"),
                    ),
                ]
            ),
            actor=TEST_ACTOR,
        )

        result = await service.list_journal_entries()

        assert result[0].total_debits == Decimal("500")
        assert result[0].total_credits == Decimal("500")
        assert result[0].is_balanced is True


@pytest.mark.unit
class TestJournalServiceCreateActorValidation:
    @pytest.mark.parametrize("actor", ["", "   ", "\t\n"])
    async def test_raises_validation_error_when_actor_is_blank(self, actor):
        service, _ = make_journal_service(chart=_simple_chart())

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(make_create_journal_input(), actor=actor)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert exc_info.value.errors == [
            FieldViolation(code=ErrorCode.REQUIRED_FIELD, field="actor", value=actor)
        ]

    async def test_does_not_persist_when_actor_is_blank(self):
        service, repo = make_journal_service(chart=_simple_chart())

        with pytest.raises(ValidationAppError):
            await service.create_journal_entry(make_create_journal_input(), actor=" ")

        assert repo.saved_entries == []

    async def test_blank_actor_consumes_no_journal_number(self):
        service, _ = make_journal_service(chart=_simple_chart())

        with pytest.raises(ValidationAppError):
            await service.create_journal_entry(make_create_journal_input(), actor="")
        created = await service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        assert created.journal_number == 1

    async def test_blank_actor_takes_precedence_over_unknown_account(self):
        service, _ = make_journal_service(chart=_simple_chart())
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Ghost Account", debit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await service.create_journal_entry(input_, actor="")

        assert exc_info.value.errors[0].code == ErrorCode.REQUIRED_FIELD

    async def test_emits_no_log_record_when_actor_is_blank(self, caplog):
        service, _ = make_journal_service(chart=_simple_chart())

        with caplog.at_level(logging.INFO):
            with pytest.raises(ValidationAppError):
                await service.create_journal_entry(
                    make_create_journal_input(), actor=""
                )

        assert [r for r in caplog.records if r.name.startswith("trutina.core")] == []

    async def test_created_log_context_carries_no_actor(self, caplog):
        service, _ = make_journal_service(chart=_simple_chart())

        with caplog.at_level(logging.INFO):
            await service.create_journal_entry(
                make_create_journal_input(), actor=TEST_ACTOR
            )

        record = next(r for r in caplog.records if r.getMessage() == "journal.created")
        assert set(record.context) == {"journal_number", "line_count"}
