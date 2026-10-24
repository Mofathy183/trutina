"""Password input rules shared by registration and login."""

import unicodedata

MAX_PASSWORD_LENGTH = 128
"""Longest raw password, in characters, that an entry point may accept.

Checked on the input exactly as typed, before ``normalize_password``, so an
oversized value is rejected before any normalization or hashing work.
"""


def normalize_password(password: str) -> str:
    """Return the exact string that is hashed and verified for a password.

    Registration and login must hash the identical string, otherwise a
    user who registered could never log in. Both therefore call this one
    function. The text is converted to Unicode NFKC form, so visually
    equivalent spellings (for example fullwidth letters) match, and then
    leading and trailing whitespace is removed. Whitespace between
    characters is kept. The conversion runs first because NFKC turns
    characters such as the no-break space and the ideographic space into
    ordinary spaces, which the strip then removes.

    A password that is empty or only whitespace comes back as an empty
    string, which callers must treat as a missing password. Case is never
    changed.

    Args:
        password: The password as typed.

    Returns:
        The normalized password.
    """
    return unicodedata.normalize("NFKC", password).strip()
