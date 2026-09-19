"""Typer command for the trial balance report.

Trial balance has exactly one action -- producing a report -- unlike
account/journal/posting, which each group several verbs (create, get,
list, ...). Per the Trial Balance Feature Plan ADR's Phase 5 note, it
is therefore registered as a single flat command on the root Typer app
(``trial-balance``) rather than as its own Typer sub-app group. If
group-consistency with account/journal/posting is preferred instead,
this is the file to convert into a one-command ``typer.Typer()`` group
mounted via ``add_typer`` -- the command body itself would not need to
change.

Unlike posting's ``post``/``get-by-account``/``get-by-journal``, the
single ``--as-of`` argument here is optional and defaults to "all
time" when omitted -- there is nothing to interactively prompt for the
way posting prompts for a required journal number, so this feature has
no prompt.py.
"""

from datetime import datetime
from typing import Annotated

import typer
from trutina.cli.composition.state import CliState
from trutina.cli.shared.boundary.error_boundary import error_boundary

from .formatter import print_trial_balance
from .handler import get_trial_balance_handler
from .parser import parse_as_of_date


def trial_balance(
    ctx: typer.Context,
    as_of: Annotated[
        str | None,
        typer.Option(
            "--as-of",
            help=(
                "Only include postings on or before this date "
                "(YYYY-MM-DD). Omit for an all-time trial balance."
            ),
        ),
    ] = None,
) -> None:
    """Show the trial balance: aggregated debit/credit totals per account."""
    state: CliState = ctx.obj

    as_of_date: datetime | None = None
    if as_of is not None:
        as_of_date = parse_as_of_date(as_of)

    with error_boundary():
        result = state.call(get_trial_balance_handler, state.context, as_of_date)

    print_trial_balance(result)
