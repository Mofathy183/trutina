"""Credential-check use case contract."""

from abc import ABC, abstractmethod

from pydantic import SecretStr
from trutina.authentication.identity import Identity


class Authenticator(ABC):
    """Turns an email and password into an ``Identity``.

    Issuing tokens is a separate step (``TokenIssuer``), so this contract
    does not depend on the access-token mechanism. ``PasswordAuthenticator``
    is the implementation.
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
            AppError: AUTH_INVALID_CREDENTIALS for wrong credentials, an
                unknown account or a disabled account (all
                indistinguishable to the caller). AUTH_THROTTLED when
                too many attempts have been made; its context may carry
                ``retry_after_seconds`` in seconds. Both codes exist in
                ``shared/errors``. ``PasswordAuthenticator`` raises
                AUTH_INVALID_CREDENTIALS; nothing raises AUTH_THROTTLED
                until throttling (M2.7).
        """
