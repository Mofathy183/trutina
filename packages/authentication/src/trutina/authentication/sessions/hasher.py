"""Session-token hashing contract."""

from abc import ABC, abstractmethod

from pydantic import SecretStr


class SessionTokenHasher(ABC):
    """Deterministic hash used to store and look up session tokens.

    Session tokens are 256-bit random values, so a fast unsalted hash is
    sufficient and lookup needs determinism. Never use ``PasswordHasher``
    for this: it is salted and deliberately slow. Formerly named for
    refresh tokens; no implementation exists yet.
    """

    @abstractmethod
    def hash(self, token: SecretStr) -> str:
        """Hash a session token.

        Args:
            token: The plaintext session token.

        Returns:
            The same string for the same token, every time.
        """
