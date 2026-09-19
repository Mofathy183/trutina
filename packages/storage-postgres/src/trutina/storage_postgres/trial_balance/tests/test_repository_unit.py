"""Unit tests for PostgresTrialBalanceRepo's pure mapping logic.

Covers reconstruction of an AccountBalanceEntry from one aggregated
result row -- requires no database. The actual GROUP BY/aggregation
SQL behavior (grouping by account_key, the as_of_date filter, result
ordering) is covered under test_repository_integration.py, since that
behavior can only be verified against a real query planner.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry
from trutina.storage_postgres.trial_balance.repository import PostgresTrialBalanceRepo


def _balance_row(
    account: str = "Cash",
    debit_total: str = "100",
    credit_total: str = "0",
) -> SimpleNamespace:
    """Stands in for a SQLAlchemy Row -- _to_domain only reads these
    three attributes, so a plain namespace is sufficient."""
    return SimpleNamespace(
        account=account,
        debit_total=Decimal(debit_total),
        credit_total=Decimal(credit_total),
    )


@pytest.mark.unit
class TestPostgresTrialBalanceRepoToDomain:
    def test_builds_account_balance_entry_from_row(self):
        row = _balance_row(account="Cash", debit_total="150", credit_total="20")

        entry = PostgresTrialBalanceRepo._to_domain(row)

        assert isinstance(entry, AccountBalanceEntry)
        assert entry.account == "Cash"
        assert entry.debit_total == Decimal("150")
        assert entry.credit_total == Decimal("20")

    def test_preserves_zero_on_the_side_with_no_activity(self):
        row = _balance_row(account="Cash", debit_total="300", credit_total="0")

        entry = PostgresTrialBalanceRepo._to_domain(row)

        assert entry.credit_total == Decimal("0")

    def test_reruns_account_name_validation(self):
        """_to_domain constructs a real AccountBalanceEntry rather than
        bypassing validation -- a corrupted or unexpectedly blank
        account value from the query must still surface as a
        ValidationError, not silently pass through."""
        row = _balance_row(account="   ")

        with pytest.raises(ValidationError):
            PostgresTrialBalanceRepo._to_domain(row)
