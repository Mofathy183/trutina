"""Credential-check use case contract."""

from abc import ABC, abstractmethod

from pydantic import SecretStr
from trutina.authentication.identity import Identity


class Authenticator(ABC):
    """Turns an email and password into an ``Identity``.

    Issuing tokens is a separate step (``TokenIssuer``), so this contract
    does not depend on the access-token mechanism.
    """

    @abstractmethod
    async def authenticate(
        self,
        *,
        email: str,
        password: SecretStr,
        client_ip: str | None,
    ) -> Identity:
        """Verify credentials.

        Args:
            email: The login email.
            password: The plaintext password.
            client_ip: Resolved client address, or ``None`` if unknown.

        Returns:
            The authenticated identity.

        Raises:
            AppError: for wrong credentials, unknown or disabled accounts
                (all indistinguishable to the caller) and for throttling.
                The ``ErrorCode`` members are added with the first
                implementation; they do not exist in ``shared/errors``
                yet.
        """
