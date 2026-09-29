"""Correlation-id generation, scoping, and validation.

Owns exactly one contextvar. A correlation id is bound for the
lifetime of one CLI command or one HTTP request via correlation_scope()
and read back by configure.py's own processor so every record emitted
inside that scope -- including ones from third-party loggers -- carries
the same id with no per-call-site plumbing required.
"""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Matches the header-safety constraint from the plan: letters, digits,
# dot, underscore, hyphen, 1-64 chars. Anything else from an inbound
# X-Request-ID is treated as untrusted and replaced, never propagated.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_correlation_id() -> str:
    """Generate a fresh, time-ordered correlation id."""
    return str(uuid.uuid7())


def is_valid_correlation_id(value: str) -> bool:
    """Whether value is safe to accept as a caller-supplied correlation id."""
    return bool(_VALID_ID.match(value))


def get_correlation_id() -> str | None:
    """Read the correlation id bound in the current scope, if any."""
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of the with-block.

    Args:
        correlation_id: A caller-supplied id (e.g. from an inbound
            X-Request-ID header) to reuse if it passes
            is_valid_correlation_id(); otherwise a new id is generated.
            None always generates a new id.

    Yields:
        The id now bound in this scope.
    """
    cid = (
        correlation_id
        if correlation_id and is_valid_correlation_id(correlation_id)
        else new_correlation_id()
    )
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)
