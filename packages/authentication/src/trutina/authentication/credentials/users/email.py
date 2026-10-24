"""Email normalization and format rules for user identity."""

import unicodedata

MAX_EMAIL_LENGTH = 254
"""Longest email address, in characters, accepted at an entry point.

Measured on the normalized address. This is the commonly used upper bound
for an address.
"""


def normalize_email(email: str) -> str:
    """Return the canonical stored form of an email address.

    Two addresses that differ only in surrounding whitespace or letter
    case identify the same login, so every user is stored and looked up
    in this one form. Uses ``casefold()``, not ``lower()``, for
    Unicode-correct caseless matching.

    This is normalization only. It does not validate email format.

    Args:
        email: The address as entered.

    Returns:
        The trimmed, case-folded address.
    """
    return email.strip().casefold()


def is_well_formed_email(email: str) -> bool:
    """Report whether an address has a plausible, minimal email shape.

    Registration uses this to refuse values that can never be a login
    identifier. Login does not call it, so an address stored before this
    rule existed can still sign in. Expects an already normalized address.
    It checks shape only: it does not confirm the address exists or can
    receive mail.

    An address passes when it is not empty, is at most ``MAX_EMAIL_LENGTH``
    characters, has no whitespace or control characters, and has exactly
    one ``@`` with text on both sides.

    Args:
        email: A normalized address.

    Returns:
        ``True`` if the address has the minimal shape.
    """
    if not email or len(email) > MAX_EMAIL_LENGTH:
        return False
    if any(ch.isspace() or unicodedata.category(ch).startswith("C") for ch in email):
        return False
    local, separator, domain = email.partition("@")
    return bool(separator and local and domain) and "@" not in domain
