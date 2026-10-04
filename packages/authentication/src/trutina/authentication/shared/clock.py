"""Time source contract."""

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Source of the current time for token expiry and throttling.

    Authentication takes time from this port, never from SQL ``now()`` or
    ``datetime.now()`` at the call site, so expiry and rotation logic is
    testable without sleeping.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time.

        Returns:
            A timezone-aware UTC datetime. Unlike the naive posting dates
            used by the accounting domain, authentication timestamps are
            always aware, so the two must never be compared directly.
        """
