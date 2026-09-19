"""Mapping helpers for trial balance API request values.

The trial balance feature accepts a single optional query parameter
(``as_of``) rather than a request body, since a trial balance is a
derived report, not something a caller submits -- mirroring
posting/mapper.py's role for that feature's own scalar-only input.

This helper normalizes the incoming route value before it crosses into
the application layer, keeping request transformation separate from
routing logic.
"""

from datetime import datetime


def to_as_of_date(as_of: datetime | None) -> datetime | None:
    """Map an ``as_of`` query parameter to the application layer.

    The value is returned unchanged because FastAPI's own ``Query(...)``
    parsing has already validated it as a real ``datetime`` (or
    ``None``) before this function runs; no additional transformation
    is required beyond that validation.

    Args:
        as_of: The validated ``as_of`` query parameter, or None.

    Returns:
        The as_of_date passed to the application layer.
    """
    return as_of
