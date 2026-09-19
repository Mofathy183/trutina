"""
CLI-argument-to-value adapter for the Trial Balance CLI feature.

Unlike account/journal, TrialBalanceService.get_trial_balance() takes a
single optional scalar (as_of_date: datetime | None) rather than an
input DTO -- there is no DTO to build here, mirroring
posting/parser.py's rationale for its own scalar-only feature (see that
module's docstring). This module validates and parses the one raw
value the trial-balance command accepts: an optional YYYY-MM-DD cutoff
date.

    Typer option (--as-of) -----> parse_as_of_date() -----> datetime

Explicitly NOT this module's responsibility:

- Business or domain validation -- date-range rules (future dates,
    the 2020-01-01 floor) are enforced by LedgerPosting/AccountBalanceEntry
    validation further downstream, not here.
- Calling services or repositories.
- Rich prompting, rendering, or console output.

This module must never be imported by service or domain code.
"""

from datetime import datetime

import typer


def parse_as_of_date(raw: str) -> datetime:
    """Resolve a raw YYYY-MM-DD date string to a datetime at midnight.

    Args:
        raw: Raw date string, as typed via the --as-of flag.

    Returns:
        The parsed date as a datetime at midnight (00:00:00).

    Raises:
        typer.BadParameter: If ``raw`` is not a valid YYYY-MM-DD date.
    """
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d")
    except ValueError:
        raise typer.BadParameter(
            f"'{raw}' is not a valid date. Use YYYY-MM-DD, e.g. 2025-01-31."
        ) from None
