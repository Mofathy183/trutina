import logging
from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.account.schemas.account import AccountCategory
from trutina.core.journal.dtos import JournalLineInput
from trutina.core.posting.dtos import PostingViewModel
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
    make_posting_feature_chart,
)
from tests.factories.posting import make_posting_service


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
class TestPostingServicePostJournalEntry:
    async def test_returns_posting_view_models(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert len(result) == 2
        assert all(isinstance(vm, PostingViewModel) for vm in result)

    async def test_returns_posting_for_each_journal_line(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("150")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("50")),
            ]
        )
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert len(result) == 3

    async def test_returns_debit_posting_view_model(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        debit_vm = next(vm for vm in result if vm.is_debit)
        assert debit_vm.account == "Cash"
        assert debit_vm.debit_amount == Decimal("100")
        assert debit_vm.credit_amount is None
        assert debit_vm.is_debit is True

    async def test_returns_credit_posting_view_model(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        credit_vm = next(vm for vm in result if not vm.is_debit)
        assert credit_vm.account == "Sales Revenue"
        assert credit_vm.credit_amount == Decimal("100")
        assert credit_vm.debit_amount is None
        assert credit_vm.is_debit is False

    async def test_returns_postings_with_journal_number(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert all(vm.journal_number == 1 for vm in result)

    async def test_returns_postings_with_posting_date(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        posting_date = datetime(2024, 6, 15)
        input_ = make_create_journal_input(posting_date=posting_date)
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert all(vm.posting_date == posting_date for vm in result)

    async def test_persists_postings_to_repo(self):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert len(posting_repo.saved_batches) == 1
        assert len(posting_repo.saved_batches[0]) == 2

    async def test_preserves_debit_amounts(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("250.00")),
                JournalLineInput(
                    account="Sales Revenue", credit_amount=Decimal("250.00")
                ),
            ]
        )
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        total_debits = sum(
            vm.debit_amount for vm in result if vm.debit_amount is not None
        )
        assert total_debits == Decimal("250.00")

    async def test_preserves_credit_amounts(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("300.00")),
                JournalLineInput(
                    account="Sales Revenue", credit_amount=Decimal("300.00")
                ),
            ]
        )
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        total_credits = sum(
            vm.credit_amount for vm in result if vm.credit_amount is not None
        )
        assert total_credits == Decimal("300.00")

    async def test_raises_when_journal_not_found(self):
        posting_service, _, _ = make_posting_service(chart=_simple_chart())

        with pytest.raises(AppError) as exc_info:
            await posting_service.post_journal_entry(999, actor=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.UNKNOWN_JOURNAL_ENTRY

    async def test_raises_when_journal_already_posted(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        with pytest.raises(AppError) as exc_info:
            await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.JOURNAL_ALREADY_POSTED

    async def test_raises_duplicate_posting_error_with_journal_context(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        with pytest.raises(AppError) as exc_info:
            await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert exc_info.value.context["value"] == "1"
        assert exc_info.value.context["resource"] == "journal_entry"
        assert exc_info.value.context["field"] == "journal_number"

    async def test_does_not_persist_postings_when_journal_not_found(self):
        posting_service, _, posting_repo = make_posting_service(chart=_simple_chart())

        with pytest.raises(AppError):
            await posting_service.post_journal_entry(999, actor=TEST_ACTOR)

        assert len(posting_repo.saved_batches) == 0

    async def test_does_not_persist_postings_when_journal_is_already_posted(self):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)
        first_batch_count = len(posting_repo.saved_batches)

        with pytest.raises(AppError):
            await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert len(posting_repo.saved_batches) == first_batch_count

    async def test_returns_postings_for_multi_line_entry(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input(
            lines=[
                JournalLineInput(account="Cash", debit_amount=Decimal("300")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("200")),
                JournalLineInput(account="Sales Revenue", credit_amount=Decimal("100")),
            ]
        )
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)

        result = await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        assert len(result) == 3
        debit_postings = [vm for vm in result if vm.is_debit]
        credit_postings = [vm for vm in result if not vm.is_debit]
        assert len(debit_postings) == 1
        assert len(credit_postings) == 2


@pytest.mark.unit
class TestPostingServiceGetByAccount:
    async def test_returns_postings_for_account(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_account("Cash")

        assert len(result) == 1
        assert result[0].account == "Cash"

    async def test_returns_empty_list_when_no_postings_for_account(self):
        posting_service, _, _ = make_posting_service(chart=_simple_chart())

        result = await posting_service.get_postings_by_account("Cash")

        assert result == []

    async def test_returns_only_postings_for_requested_account(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_account("Sales Revenue")

        assert len(result) == 1
        assert result[0].account == "Sales Revenue"

    async def test_returns_posting_view_models(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_account("Cash")

        assert all(isinstance(vm, PostingViewModel) for vm in result)

    async def test_returns_postings_for_account_case_insensitively(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result_lower = await posting_service.get_postings_by_account("cash")
        result_upper = await posting_service.get_postings_by_account("CASH")

        assert len(result_lower) == 1
        assert len(result_upper) == 1
        assert result_lower[0].account == "Cash"
        assert result_upper[0].account == "Cash"


@pytest.mark.unit
class TestPostingServiceGetByJournalNumber:
    async def test_returns_postings_for_journal_number(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_journal_number(1)

        assert len(result) == 2

    async def test_returns_empty_list_when_no_postings_for_journal_number(self):
        posting_service, _, _ = make_posting_service(chart=_simple_chart())

        result = await posting_service.get_postings_by_journal_number(999)

        assert result == []

    async def test_returns_only_postings_for_journal_number(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_journal_number(1)

        assert all(vm.journal_number == 1 for vm in result)

    async def test_returns_posting_view_models(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        input_ = make_create_journal_input()
        await journal_service.create_journal_entry(input_, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        result = await posting_service.get_postings_by_journal_number(1)

        assert all(isinstance(vm, PostingViewModel) for vm in result)

    async def test_separates_postings_by_journal_number(self):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )

        input1 = make_create_journal_input(description="First")
        input2 = make_create_journal_input(description="Second")

        await journal_service.create_journal_entry(input1, actor=TEST_ACTOR)
        await journal_service.create_journal_entry(input2, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor=TEST_ACTOR)
        await posting_service.post_journal_entry(2, actor=TEST_ACTOR)

        result1 = await posting_service.get_postings_by_journal_number(1)
        result2 = await posting_service.get_postings_by_journal_number(2)

        assert len(result1) == 2
        assert len(result2) == 2
        assert all(vm.journal_number == 1 for vm in result1)
        assert all(vm.journal_number == 2 for vm in result2)


@pytest.mark.unit
class TestPostingServicePostActorValidation:
    @pytest.mark.parametrize("actor", ["", "   ", "\t\n"])
    async def test_raises_validation_error_when_actor_is_blank(self, actor):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        with pytest.raises(ValidationAppError) as exc_info:
            await posting_service.post_journal_entry(1, actor=actor)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert exc_info.value.errors == [
            FieldViolation(code=ErrorCode.REQUIRED_FIELD, field="actor", value=actor)
        ]

    async def test_does_not_persist_when_actor_is_blank(self):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=_simple_chart()
        )
        await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        with pytest.raises(ValidationAppError):
            await posting_service.post_journal_entry(1, actor=" ")

        assert posting_repo.saved_batches == []

    async def test_blank_actor_takes_precedence_over_unknown_journal_number(self):
        posting_service, _, _ = make_posting_service(chart=_simple_chart())

        with pytest.raises(ValidationAppError) as exc_info:
            await posting_service.post_journal_entry(999, actor="")

        assert exc_info.value.errors[0].code == ErrorCode.REQUIRED_FIELD

    async def test_emits_no_log_record_when_actor_is_blank(self, caplog):
        posting_service, _, _ = make_posting_service(chart=_simple_chart())

        with caplog.at_level(logging.INFO):
            with pytest.raises(ValidationAppError):
                await posting_service.post_journal_entry(1, actor="")

        assert [r for r in caplog.records if r.name.startswith("trutina.core")] == []

    async def test_created_log_context_carries_no_actor(self, caplog):
        posting_service, journal_service, _ = make_posting_service(
            chart=_simple_chart()
        )
        await journal_service.create_journal_entry(
            make_create_journal_input(), actor=TEST_ACTOR
        )

        with caplog.at_level(logging.INFO):
            await posting_service.post_journal_entry(1, actor=TEST_ACTOR)

        record = next(r for r in caplog.records if r.getMessage() == "posting.created")
        assert set(record.context) == {"journal_number", "line_count"}


@pytest.mark.unit
class TestPostingServiceCreatedBy:
    async def test_passes_actor_to_repo_as_created_by(self, create_input):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=make_posting_feature_chart()
        )
        await journal_service.create_journal_entry(create_input, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor="system:pre-auth:cli")

        assert posting_repo.saved_created_by == ["system:pre-auth:cli"]

    async def test_records_one_created_by_per_batch_not_per_posting(self, create_input):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=make_posting_feature_chart()
        )
        await journal_service.create_journal_entry(create_input, actor=TEST_ACTOR)

        await posting_service.post_journal_entry(1, actor="system:pre-auth:api")

        assert len(posting_repo.saved_batches[0]) == 2
        assert posting_repo.saved_created_by == ["system:pre-auth:api"]

    async def test_blank_actor_records_nothing(self, create_input):
        posting_service, journal_service, posting_repo = make_posting_service(
            chart=make_posting_feature_chart()
        )
        await journal_service.create_journal_entry(create_input, actor=TEST_ACTOR)

        with pytest.raises(ValidationAppError) as exc_info:
            await posting_service.post_journal_entry(1, actor="   ")

        assert exc_info.value.errors[0].code == ErrorCode.REQUIRED_FIELD
        assert posting_repo.saved_created_by == []
        assert posting_repo.saved_batches == []
