"""
Shared accounting validation and normalization rules.

Provides reusable business-rule functions used by account, journal,
and posting domain models. These rules remain independent of schema
implementations so the same accounting behavior is applied consistently
across validation workflows, service operations, and chart lookups.
"""

import re
from decimal import Decimal

# Account names must begin with a letter.
# Letters, digits, and spaces may appear freely.
# Supported separators (&, -, ', ., /) may appear only individually.
ACCOUNT_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9 ]*(?:[&\-'./][A-Za-z0-9 ]+)*$"


def clean_account_name(value: str) -> str | None:
    """Validate and normalize an account name.

    Account names are used to identify ledger accounts throughout the
    accounting system. To ensure consistent matching and prevent invalid
    references, account names are restricted to a permitted character
    set defined by ``ACCOUNT_NAME_PATTERN``.

    Leading and trailing whitespace is removed before validation.
    Original casing is preserved; case-insensitive matching is handled
    separately via :func:`account_lookup_key`.

    Args:
        value: User-provided account name.

    Returns:
        The trimmed account name when validation succeeds, otherwise
        ``None``.

    Notes:
        The controlled format keeps account references predictable and
        consistently matchable throughout the chart of accounts.
    """
    cleaned = value.strip()

    if not re.fullmatch(ACCOUNT_NAME_PATTERN, cleaned):
        return None

    return cleaned


def is_valid_line_amounts(debit: Decimal, credit: Decimal) -> bool:
    """Determine whether a journal line represents exactly one side of a transaction.

    A journal line must represent exactly one side of a double-entry
    accounting transaction. A line may contain either a debit amount or
    a credit amount, but not both.

    Allowing both amounts would cause a single journal line to represent
    two sides of a transaction simultaneously. Allowing neither would
    create a line that contributes nothing to the journal entry.

    Valid examples:

    - Debit = 100, Credit = 0
    - Debit = 0, Credit = 100

    Invalid examples:

    - Debit = 100, Credit = 100
    - Debit = 0, Credit = 0

    Args:
        debit: Debit amount recorded on the journal line.
        credit: Credit amount recorded on the journal line.

    Returns:
        ``True`` if the journal line represents a valid posting,
        otherwise ``False``.
    """
    return (debit > 0) ^ (credit > 0)


def account_lookup_key(name: str) -> str:
    """Return the canonical lookup key for an account name reference.

    Two account names with the same lookup key are treated as the same
    account for matching and uniqueness purposes, regardless of display
    casing. This allows account references and chart entries to be
    compared consistently while preserving their original presentation.

    Args:
        name: A normalized account name already validated by
            :func:`clean_account_name`.

    Returns:
        The case-folded lookup key.
    """
    return name.casefold()


def is_non_blank_actor(actor: str) -> bool:
    """Whether an actor string names someone: not empty, not whitespace-only.

    Every write must be attributable to a caller. A blank actor would
    record no one, and the attribution could never be recovered later.

    This is a presence check only. It never inspects the format (UUID,
    ``system:`` prefix); that belongs to the API and CLI handlers, so the
    accounting layers never learn what an identity looks like.

    Args:
        actor: The caller-supplied actor string.

    Returns:
        True if ``actor`` contains at least one non-whitespace character.
    """
    return bool(actor.strip())
