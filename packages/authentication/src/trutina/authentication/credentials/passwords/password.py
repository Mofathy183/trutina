"""Password hashing contract."""

from abc import ABC, abstractmethod

from pydantic import SecretStr


class PasswordHasher(ABC):
    """Hashes and verifies user passwords.

    Hashing is deliberately slow and CPU-bound. The implementation, not
    the caller, owns running it off the event loop and bounding how many
    run at once, so no caller can forget either. Distinct from
    ``RefreshTokenHasher``: a password hash must never be used to look up
    a token.
    """

    @abstractmethod
    async def hash(self, password: SecretStr) -> str:
        """Hash a password for storage.

        Args:
            password: The plaintext password.

        Returns:
            A self-describing hash string including salt and parameters.
        """

    @abstractmethod
    async def verify(self, password: SecretStr, password_hash: str) -> bool:
        """Check a password against a stored hash.

        Args:
            password: The plaintext password.
            password_hash: A hash previously returned by ``hash``.

        Returns:
            ``True`` only on a match. A mismatch and a malformed hash both
            return ``False`` rather than raising, so the unknown-user path
            (verifying against a dummy hash) behaves like a wrong password.
        """

    @abstractmethod
    def needs_rehash(self, password_hash: str) -> bool:
        """Report whether a stored hash uses outdated parameters.

        Args:
            password_hash: A stored hash.

        Returns:
            ``True`` if the hash should be recomputed after a successful
            login.
        """
