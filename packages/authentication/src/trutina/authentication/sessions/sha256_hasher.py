"""SHA-256 session-token hasher.

The concrete ``SessionTokenHasher``. Lives beside the contract in its own
module so the contract module never imports a cryptographic library. Part
of ``trutina-authentication``; needs only the standard library.
"""

import hashlib

from pydantic import SecretStr

from .hasher import SessionTokenHasher


class Sha256SessionTokenHasher(SessionTokenHasher):
    """Hex SHA-256 of the UTF-8 session token, with no salt and no pepper.

    Session tokens are 256-bit random values, so a fast unsalted hash is
    enough to keep a stolen database from yielding usable tokens, and the
    lookup needs the same output for the same token every time. Never use
    it for passwords: use ``PasswordHasher``.
    """

    def hash(self, token: SecretStr) -> str:
        """Hash a session token.

        Args:
            token: The plaintext session token.

        Returns:
            The 64-character lowercase hex digest. The token never appears
            in it.
        """
        return hashlib.sha256(token.get_secret_value().encode("utf-8")).hexdigest()
