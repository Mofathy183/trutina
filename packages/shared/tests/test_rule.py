from decimal import Decimal

import pytest
from trutina.shared.rule import (
    account_lookup_key,
    clean_account_name,
    is_non_blank_actor,
    is_valid_line_amounts,
)


@pytest.mark.unit
class TestCleanAccountName:
    def test_returns_trimmed_name(self):
        value = "  Cash  "

        result = clean_account_name(value)

        assert result == "Cash"

    @pytest.mark.parametrize(
        "name",
        [
            "Cash",
            "Accounts Receivable",
            "Cash & Cash Equivalents",
            "Owner's Equity",
            "Pre-Paid Expenses",
            "Property/Equipment",
            "Account.Receivable",
            "Revenue 2025",
        ],
    )
    def test_accepts_valid_account_names(self, name):

        result = clean_account_name(name)

        assert result == name

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "   ",
        ],
    )
    def test_returns_none_when_name_is_empty_or_whitespace_only(self, name):

        result = clean_account_name(name)

        assert result is None

    @pytest.mark.parametrize(
        "name",
        [
            "1Cash",
            "9 Revenue",
            "123",
        ],
    )
    def test_returns_none_when_name_does_not_start_with_letter(self, name):

        result = clean_account_name(name)

        assert result is None

    @pytest.mark.parametrize(
        "name",
        [
            "Cash@@",
            "Cash#",
            "Cash$",
            "Cash%",
            "Cash!",
            "Cash(",
            "Cash)",
            "Cash_Account",
        ],
    )
    def test_returns_none_when_name_contains_unsupported_characters(
        self,
        name,
    ):

        result = clean_account_name(name)

        assert result is None

    @pytest.mark.parametrize(
        "name",
        [
            "Cash--Account",
            "Cash''Account",
            "Cash//Account",
            "Cash..Account",
            "Cash&&Account",
            "Cash-&Account",
            "Cash/.Account",
        ],
    )
    def test_returns_none_when_special_characters_are_consecutive(
        self,
        name,
    ):

        result = clean_account_name(name)

        assert result is None

    @pytest.mark.parametrize(
        "name",
        [
            "Cash-",
            "Cash&",
            "Cash'",
            "Cash.",
            "Cash/",
        ],
    )
    def test_returns_none_when_name_ends_with_special_character(
        self,
        name,
    ):

        result = clean_account_name(name)

        assert result is None


@pytest.mark.unit
class TestIsValidLineAmounts:
    def test_accepts_debit_only_amount(self):
        debit = Decimal("100")
        credit = Decimal("0")

        result = is_valid_line_amounts(
            debit=debit,
            credit=credit,
        )

        assert result is True

    def test_accepts_credit_only_amount(self):
        debit = Decimal("0")
        credit = Decimal("100")

        result = is_valid_line_amounts(
            debit=debit,
            credit=credit,
        )

        assert result is True

    @pytest.mark.parametrize(
        ("debit", "credit"),
        [
            (Decimal("100"), Decimal("100")),
            (Decimal("0.01"), Decimal("0.01")),
            (Decimal("999999"), Decimal("1")),
        ],
    )
    def test_rejects_when_both_amounts_are_positive(
        self,
        debit,
        credit,
    ):

        result = is_valid_line_amounts(
            debit=debit,
            credit=credit,
        )

        assert result is False

    def test_rejects_when_both_amounts_are_zero(self):
        debit = Decimal("0")
        credit = Decimal("0")

        result = is_valid_line_amounts(
            debit=debit,
            credit=credit,
        )

        assert result is False

    @pytest.mark.parametrize(
        ("debit", "credit"),
        [
            (Decimal("0.01"), Decimal("0")),
            (Decimal("0"), Decimal("0.01")),
            (Decimal("100.01"), Decimal("0")),
            (Decimal("0"), Decimal("100.01")),
        ],
    )
    def test_accepts_boundary_positive_amounts(
        self,
        debit,
        credit,
    ):

        result = is_valid_line_amounts(
            debit=debit,
            credit=credit,
        )

        assert result is True


@pytest.mark.unit
class TestAccountLookupKey:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Cash", "cash"),
            ("CASH", "cash"),
            ("cAsH", "cash"),
            ("Sales Revenue", "sales revenue"),
        ],
    )
    def test_returns_casefolded_lookup_key(
        self,
        value,
        expected,
    ):
        result = account_lookup_key(value)

        assert result == expected

    def test_returns_same_value_when_already_lowercase(self):
        result = account_lookup_key("cash")

        assert result == "cash"

    def test_returns_same_lookup_key_for_different_casing(self):
        first = account_lookup_key("Cash")
        second = account_lookup_key("CASH")
        third = account_lookup_key("cAsH")

        assert first == second == third

    def test_returns_unicode_casefolded_lookup_key(self):
        result = account_lookup_key("Straße")

        assert result == "strasse"


@pytest.mark.unit
class TestIsNonBlankActor:
    @pytest.mark.parametrize("actor", ["", " ", "   ", "\t", "\n", "\t\n "])
    def test_rejects_blank_actor(self, actor):
        assert is_non_blank_actor(actor) is False

    @pytest.mark.parametrize(
        "actor",
        ["system:test", "a", " padded ", "1b4e28ba-2fa1-11d2-883f-0016d3cca427"],
    )
    def test_accepts_actor_with_content(self, actor):
        assert is_non_blank_actor(actor) is True
