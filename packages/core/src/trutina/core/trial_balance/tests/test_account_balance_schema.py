from decimal import Decimal

import pytest
from pydantic import ValidationError
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry
from trutina.shared.errors import ErrorCode

from tests.factories import make_account_balance_entry


@pytest.mark.unit
class TestAccountBalanceEntry:
    def test_creates_valid_entry(self):
        entry = make_account_balance_entry(
            account="Cash",
            debit_total=Decimal("150.00"),
            credit_total=Decimal("50.00"),
        )

        assert entry.account == "Cash"
        assert entry.debit_total == Decimal("150.00")
        assert entry.credit_total == Decimal("50.00")

    def test_accepts_normalized_account_name(self):
        entry = make_account_balance_entry(account="  Cash  ")

        assert entry.account == "Cash"

    def test_accepts_zero_totals_on_both_sides(self):
        """AccountBalanceEntry does not enforce LedgerPosting's
        single-sidedness rule -- an account legitimately carries both
        debit and credit activity. Zero on both sides is structurally
        unusual (it implies a grouped account_key with no rows, which
        the repository contract never produces) but is not something
        this schema is responsible for preventing -- see repo.py's own
        contract docstring for where that guarantee actually lives.
        """
        entry = make_account_balance_entry(
            debit_total=Decimal("0"), credit_total=Decimal("0")
        )

        assert entry.debit_total == Decimal("0")
        assert entry.credit_total == Decimal("0")

    def test_accepts_both_sides_positive(self):
        """Unlike LedgerPosting, both totals may be positive at once --
        this is the normal case for any account with mixed activity."""
        entry = make_account_balance_entry(
            debit_total=Decimal("300"), credit_total=Decimal("120")
        )

        assert entry.debit_total == Decimal("300")
        assert entry.credit_total == Decimal("120")

    def test_raises_validation_error_when_account_name_is_blank(self):
        with pytest.raises(ValidationError) as exc_info:
            make_account_balance_entry(account="   ")

        errors = exc_info.value.errors()

        assert any(error["type"] == ErrorCode.INVALID_ACCOUNT_NAME for error in errors)

    def test_raises_validation_error_when_account_name_contains_invalid_characters(
        self,
    ):
        with pytest.raises(ValidationError) as exc_info:
            make_account_balance_entry(account="Cash@@")

        errors = exc_info.value.errors()

        assert any(error["type"] == ErrorCode.INVALID_ACCOUNT_NAME for error in errors)

    def test_raises_validation_error_when_account_name_is_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            AccountBalanceEntry(
                account="A",
                debit_total=Decimal("100"),
                credit_total=Decimal("0"),
            )

        errors = exc_info.value.errors()

        assert any(error["type"] == ErrorCode.STRING_TOO_SHORT for error in errors)

    def test_raises_validation_error_when_account_name_is_too_long(self):
        account_name = "A" * 101

        with pytest.raises(ValidationError) as exc_info:
            AccountBalanceEntry(
                account=account_name,
                debit_total=Decimal("100"),
                credit_total=Decimal("0"),
            )

        errors = exc_info.value.errors()

        assert any(error["type"] == ErrorCode.STRING_TOO_LONG for error in errors)

    @pytest.mark.parametrize(
        "field_name",
        ["debit_total", "credit_total"],
    )
    def test_raises_validation_error_when_a_total_is_negative(self, field_name):
        payload = {
            "account": "Cash",
            "debit_total": Decimal("100"),
            "credit_total": Decimal("0"),
        }
        payload[field_name] = Decimal("-1")

        with pytest.raises(ValidationError) as exc_info:
            AccountBalanceEntry(**payload)

        errors = exc_info.value.errors()

        assert any(
            error["type"] == ErrorCode.GREATER_THAN_EQUAL
            and error["loc"] == (field_name,)
            for error in errors
        )

    def test_raises_when_frozen_field_is_mutated(self):
        entry = make_account_balance_entry()

        with pytest.raises(ValidationError) as exc_info:
            entry.account = "Equipment"  # ty:ignore[invalid-assignment]

        errors = exc_info.value.errors()

        assert any(error["type"] == "frozen_instance" for error in errors)
