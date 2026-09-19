from datetime import datetime

import pytest
from trutina.api.features.trial_balance.handler import get_trial_balance_handler
from trutina.core.trial_balance.dtos import TrialBalanceViewModel

from tests.factories import make_account_balance_entry, make_trial_balance_service


@pytest.mark.unit
class TestGetTrialBalanceHandler:
    async def test_returns_trial_balance_view_model(self):
        service, _repo = make_trial_balance_service(
            entries=[make_account_balance_entry()]
        )

        result = await get_trial_balance_handler(service, None)

        assert isinstance(result, TrialBalanceViewModel)
        assert len(result.entries) == 1

    async def test_passes_as_of_date_through_to_the_service(self):
        service, repo = make_trial_balance_service()
        cutoff = datetime(2025, 1, 1)

        await get_trial_balance_handler(service, cutoff)

        assert repo.calls == [cutoff]

    async def test_defaults_to_all_time_when_as_of_date_is_none(self):
        service, repo = make_trial_balance_service()

        await get_trial_balance_handler(service, None)

        assert repo.calls == [None]

    async def test_returns_empty_entries_when_no_postings_exist(self):
        service, _repo = make_trial_balance_service()

        result = await get_trial_balance_handler(service, None)

        assert result.entries == []
