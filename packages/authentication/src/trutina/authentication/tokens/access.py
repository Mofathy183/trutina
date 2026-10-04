"""Access-token contracts.

Provisional until the M3 ADR settles whether access tokens are JWTs or
one opaque session mechanism (decision D1).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr
from trutina.authentication.identity import Identity


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A short-lived credential for API calls.

    Attributes:
        value: The opaque token string handed to the client.
        expires_at: Timezone-aware UTC expiry.
    """

    value: SecretStr
    expires_at: datetime


class TokenIssuer(ABC):
    """Creates access tokens for an authenticated identity."""

    @abstractmethod
    def issue_access_token(self, identity: Identity) -> AccessToken:
        """Issue an access token.

        Args:
            identity: The authenticated principal.

        Returns:
            The new access token.
        """


class TokenVerifier(ABC):
    """Validates access tokens presented by clients."""

    @abstractmethod
    def verify_access_token(self, token: SecretStr) -> Identity | None:
        """Validate a presented access token.

        Args:
            token: The token as presented.

        Returns:
            The identity it was issued for, or ``None`` for any token that
            is malformed, tampered with, expired or otherwise unacceptable.
            The caller maps ``None`` to its own 401 response.
        """
