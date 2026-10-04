"""Authentication event contract.

Gives authentication code a place to report security-relevant facts
(refresh reuse, throttling, status-check failures) before any logging
or alerting pipeline consumes them.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class AuthEvent:
    """A structured, secret-free record of something that happened.

    Attributes:
        name: Dotted event name, never a formatted sentence
            (for example ``auth.refresh_reused``).
        context: String-only details, frozen at construction. Never
            include a password, token, hash or key.
    """

    name: str
    context: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


class AuthEventSink(ABC):
    """Receiver of ``AuthEvent`` records."""

    @abstractmethod
    def emit(self, event: AuthEvent) -> None:
        """Accept one event.

        Implementations must not raise: reporting an event never fails the
        authentication operation that produced it.

        Args:
            event: The event to record.
        """


class NoOpAuthEventSink(AuthEventSink):
    """Default sink that discards every event."""

    def emit(self, event: AuthEvent) -> None:
        return None
