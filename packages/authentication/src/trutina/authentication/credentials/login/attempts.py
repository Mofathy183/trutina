"""Login-attempt tracking contract.

Records failed logins so a service can throttle them. Frozen in M2.4:
the policy (thresholds, windows, retry delay) stays in the service, never
in an adapter.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class LoginAttemptRepo(ABC):
    """Records failed logins so the service can throttle them.

    Attempts are keyed on client IP and email together, so one address
    cannot lock out an account and one account is not exposed to every
    address. The email is matched in its normalized form
    (``normalize_email()``: trimmed, then case-folded), so two spellings of
    one address count as one. The IP is matched exactly as given.

    All timestamps are timezone-aware UTC from ``Clock``. They must never
    be compared with the accounting domain's naive posting dates.

    Adapters must stay async, hold no throttling policy, and translate
    storage failures to ``AppError`` (``STORAGE_UNAVAILABLE`` or
    ``STORAGE_TIMEOUT``) before they cross the boundary. No method raises a
    domain error: every one is a no-op or returns zero on a miss.
    """

    @abstractmethod
    async def record_failure(self, *, ip: str, email: str, at: datetime) -> None:
        """Record one failed login.

        Args:
            ip: Client address ("unknown" when it cannot be determined).
            email: The email attempted; stored normalized.
            at: When the failure happened, as aware UTC.
        """

    @abstractmethod
    async def count_failures(self, *, ip: str, email: str, since: datetime) -> int:
        """Count failures for this IP and email since a moment.

        Args:
            ip: Client address.
            email: The email attempted; matched normalized.
            since: Inclusive lower bound.

        Returns:
            The number of recorded failures, zero when there are none.
        """

    @abstractmethod
    async def clear(self, *, ip: str, email: str) -> None:
        """Forget failures for this IP and email (after a success).

        Only this IP and email pair is affected. Clearing a pair with no
        failures is a no-op.

        Args:
            ip: Client address.
            email: The email attempted; matched normalized.
        """

    @abstractmethod
    async def purge_before(self, cutoff: datetime) -> int:
        """Delete failures older than a cutoff, for every IP and email.

        Args:
            cutoff: Records strictly older than this are removed; a record
                stamped exactly at the cutoff is kept.

        Returns:
            The number of rows removed.
        """
