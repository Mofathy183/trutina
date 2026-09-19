from datetime import datetime

import pytest
from trutina.cli.features.trial_balance.handler import get_trial_balance_handler
from trutina.core.trial_balance import TrialBalanceViewModel

from tests.factories import (
    make_account_balance_entry,
    make_fake_cli_context,
    make_fake_trial_balance_repo,
)


@pytest.mark.unit
class TestGetTrialBalanceHandler:
    async def test_returns_trial_balance_view_model(self):
        repo = make_fake_trial_balance_repo(entries=[make_account_balance_entry()])
        ctx = make_fake_cli_context(trial_balance_repo=repo)

        result = await get_trial_balance_handler(ctx, None)

        assert isinstance(result, TrialBalanceViewModel)
        assert len(result.entries) == 1

    async def test_passes_as_of_date_through_to_the_repo(self):
        repo = make_fake_trial_balance_repo()
        ctx = make_fake_cli_context(trial_balance_repo=repo)
        cutoff = datetime(2025, 1, 1)

        await get_trial_balance_handler(ctx, cutoff)

        assert repo.calls == [cutoff]

    async def test_defaults_to_all_time_when_as_of_date_is_none(self):
        repo = make_fake_trial_balance_repo()
        ctx = make_fake_cli_context(trial_balance_repo=repo)

        await get_trial_balance_handler(ctx, None)

        assert repo.calls == [None]

    async def test_returns_empty_entries_when_no_postings_exist(self):
        ctx = make_fake_cli_context()

        result = await get_trial_balance_handler(ctx, None)

        assert result.entries == []
        assert result.is_balanced is True
