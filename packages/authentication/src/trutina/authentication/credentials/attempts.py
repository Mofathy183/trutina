"""Login-attempt tracking contract.

Provisional: the shape is finalized in M2 with the throttling logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class LoginAttemptRepo(ABC):
    """Records failed logins so the service can throttle them.

    Attempts are keyed on client IP and email together, so one address
    cannot lock out an account and one account is not exposed to every
    address. Adapters must stay async and hold no throttling policy.
    """

    @abstractmethod
    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        """Record one failed login.

        Args:
            ip: Client address ("unknown" when it cannot be determined).
            email: The email attempted; matched case-insensitively.
            at: When the failure happened.
        """

    @abstractmethod
    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        """Count failures for this IP and email since a moment.

        Args:
            ip: Client address.
            email: The email attempted.
            since: Inclusive lower bound.

        Returns:
            The number of recorded failures.
        """

    @abstractmethod
    async def clear(self, *, ip: str, email: str) -> None:
        """Forget failures for this IP and email (after a success).

        Args:
            ip: Client address.
            email: The email attempted.
        """

    @abstractmethod
    async def purge_before(self, cutoff: datetime) -> int:
        """Delete failures older than a cutoff.

        Args:
            cutoff: Records strictly older than this are removed.

        Returns:
            The number of rows removed.
        """
