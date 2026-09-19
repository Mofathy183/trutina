from datetime import datetime
from decimal import Decimal

import pytest
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

from tests.factories import make_account_balance_entry, make_trial_balance_service


@pytest.mark.unit
class TestTrialBalanceServiceGetTrialBalance:
    async def test_returns_a_trial_balance_view_model(self):
        service, _repo = make_trial_balance_service()

        result = await service.get_trial_balance()

        assert isinstance(result, TrialBalanceViewModel)

    async def test_returns_entries_from_the_repo_unchanged(self):
        entries = [
            make_account_balance_entry(account="Cash"),
            make_account_balance_entry(account="Sales Revenue"),
        ]
        service, _repo = make_trial_balance_service(entries=entries)

        result = await service.get_trial_balance()

        assert result.entries == entries

    async def test_returns_empty_entries_when_repo_has_nothing_in_scope(self):
        service, _repo = make_trial_balance_service(entries=[])

        result = await service.get_trial_balance()

        assert result.entries == []
        assert result.is_balanced is True

    async def test_defaults_as_of_date_to_none_when_omitted(self):
        service, repo = make_trial_balance_service()

        await service.get_trial_balance()

        assert repo.calls == [None]

    async def test_passes_as_of_date_through_to_the_repo(self):
        as_of = datetime(2025, 6, 30)
        service, repo = make_trial_balance_service()

        await service.get_trial_balance(as_of_date=as_of)

        assert repo.calls == [as_of]

    async def test_view_models_as_of_date_matches_the_requested_value(self):
        as_of = datetime(2025, 6, 30)
        service, _repo = make_trial_balance_service()

        result = await service.get_trial_balance(as_of_date=as_of)

        assert result.as_of_date == as_of

    async def test_view_models_as_of_date_is_none_when_omitted(self):
        service, _repo = make_trial_balance_service()

        result = await service.get_trial_balance()

        assert result.as_of_date is None

    async def test_view_model_totals_are_derived_from_repo_entries(self):
        entries = [
            make_account_balance_entry(
                account="Cash", debit_total=Decimal("100"), credit_total=Decimal("0")
            ),
            make_account_balance_entry(
                account="Sales Revenue",
                debit_total=Decimal("0"),
                credit_total=Decimal("100"),
            ),
        ]
        service, _repo = make_trial_balance_service(entries=entries)

        result = await service.get_trial_balance()

        assert result.total_debits == Decimal("100")
        assert result.total_credits == Decimal("100")
        assert result.is_balanced is True

    async def test_each_call_is_recorded_independently_on_repeated_calls(self):
        """Calling the service twice with different as_of_date values
        must not lose or overwrite the first call's record -- useful
        for catching an accidental shared-state bug in a future
        refactor of the fake or the service."""
        service, repo = make_trial_balance_service()
        first = datetime(2025, 1, 1)
        second = datetime(2025, 6, 30)

        await service.get_trial_balance(as_of_date=first)
        await service.get_trial_balance(as_of_date=second)

        assert repo.calls == [first, second]
