"""Email normalization for user identity."""


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
