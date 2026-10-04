"""Per-write user status contract."""

from abc import ABC, abstractmethod
from uuid import UUID

from .models import AccessState


class UserStatusChecker(ABC):
    """Reads the current access state of a user from the source of truth.

    Called on every write route so a disabled user stops acting at once,
    while reads stay stateless. Kept behind a port so a short-lived cache
    can be added later without changing callers.
    """

    @abstractmethod
    async def get_access_state(self, subject_id: UUID) -> AccessState:
        """Return the user's current access state.

        Args:
            subject_id: The user to check.

        Returns:
            The state. An unknown user yields ``is_active=False``, because
            callers treat a missing and a disabled user identically.
        """
