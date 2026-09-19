"""Integration tests for the trial-balance CLI command against real PostgreSQL.

portal.call(...) is synchronous -- it blocks the calling thread until
the portal's own event loop completes the work and returns the plain
result directly, not a coroutine. Every call site below is therefore
plain, unawaited portal.call(...), matching how CliState.call() and
command.py themselves invoke it, and mirroring posting's own
test_command_integration.py exactly.
"""

import pytest
from trutina.cli.composition.app import app
from trutina.cli.shared.ui import console
from trutina.core.account.schemas.account import AccountCategory

from tests.factories import make_create_account_input, make_create_journal_input


def _invoke(runner, state, args, input=None):
    with console.capture() as capture:
        result = runner.invoke(app, args, obj=state, input=input)
    return result, capture.get()


@pytest.fixture
def seeded_real_state(real_cli_state):
    """Seeds two accounts and one posted journal entry through the
    real, Postgres-backed services -- not through the CLI -- so the
    trial-balance command under test has real persisted data to read.
    """
    account_service = real_cli_state.portal.call(
        real_cli_state.context.get_account_service
    )
    journal_service = real_cli_state.portal.call(
        real_cli_state.context.get_journal_service
    )
    posting_service = real_cli_state.portal.call(
        real_cli_state.context.get_posting_service
    )

    real_cli_state.portal.call(
        account_service.create_account,
        make_create_account_input(code="1001", name="Cash"),
    )
    real_cli_state.portal.call(
        account_service.create_account,
        make_create_account_input(
            code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
        ),
    )
    entry = real_cli_state.portal.call(
        journal_service.create_journal_entry, make_create_journal_input()
    )
    real_cli_state.portal.call(posting_service.post_journal_entry, entry.journal_number)

    return real_cli_state


@pytest.mark.integration
class TestTrialBalanceCommandIntegration:
    def test_shows_trial_balance_against_real_postgres(
        self, cli_runner, seeded_real_state
    ):
        result, output = _invoke(cli_runner, seeded_real_state, ["trial-balance"])

        assert result.exit_code == 0
        assert "Cash" in output
        assert "Sales Revenue" in output
        assert "Balanced: Yes" in output

    def test_shows_no_postings_found_on_fresh_database(
        self, cli_runner, real_cli_state
    ):
        result, output = _invoke(cli_runner, real_cli_state, ["trial-balance"])

        assert result.exit_code == 0
        assert "No postings found" in output

    def test_as_of_flag_excludes_later_postings(self, cli_runner, real_cli_state):
        account_service = real_cli_state.portal.call(
            real_cli_state.context.get_account_service
        )
        journal_service = real_cli_state.portal.call(
            real_cli_state.context.get_journal_service
        )
        posting_service = real_cli_state.portal.call(
            real_cli_state.context.get_posting_service
        )

        real_cli_state.portal.call(
            account_service.create_account,
            make_create_account_input(code="1001", name="Cash"),
        )
        real_cli_state.portal.call(
            account_service.create_account,
            make_create_account_input(
                code="4001", name="Sales Revenue", category=AccountCategory.REVENUE
            ),
        )
        from datetime import datetime

        entry = real_cli_state.portal.call(
            journal_service.create_journal_entry,
            make_create_journal_input(posting_date=datetime(2025, 6, 1)),
        )
        real_cli_state.portal.call(
            posting_service.post_journal_entry, entry.journal_number
        )

        result, output = _invoke(
            cli_runner, real_cli_state, ["trial-balance", "--as-of", "2025-01-01"]
        )

        assert result.exit_code == 0
        assert "No postings found" in output
