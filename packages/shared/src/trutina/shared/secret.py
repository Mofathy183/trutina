"""Credential-shaped field detection and input redaction.

A validation failure on a credential must report that the field was
wrong, never what the caller typed: a password rejected for being too
short is still a password. This module is the one place the shared
error layer decides which fields are credentials and how a rejected
input is rendered safely. It is consumed by `errors/translators.py`
when it builds `FieldViolation.value`.

Detection is key-based: a name is credential-shaped when its
lower-cased text contains one of `SECRET_FIELD_MARKERS`. The same
markers (and the same `"***REDACTED***"` mask) are used by
trutina-observability's log redaction. That package cannot be imported
from here, so the two lists are kept in sync by hand; change both
together.

Depends on nothing else in the workspace. Must not import from `cli/`,
`api/`, `core/` or `observability/`.
"""

from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "***REDACTED***"

SECRET_FIELD_MARKERS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "authorization",
    "credential",
    "api_key",
)


def is_secret_name(name: str) -> bool:
    """Whether a single field or key name looks like a credential.

    Matching is by substring on the lower-cased name, so `new_password`
    and `refresh_token` match without being listed. Over-matching is
    accepted: masking a harmless value costs a diagnostic, leaking a
    credential costs far more.

    Args:
        name: One field or dict-key name.

    Returns:
        True if the name contains any of `SECRET_FIELD_MARKERS`.
    """
    lowered = name.lower()
    return any(marker in lowered for marker in SECRET_FIELD_MARKERS)


def is_secret_location(loc: Iterable[str | int]) -> bool:
    """Whether any segment of a Pydantic error location is credential-shaped.

    Every segment is checked, not only the last, so a failure on
    `credentials.value` is covered by its parent's name.

    Args:
        loc: The `loc` tuple of one Pydantic error (field names and
            list indexes).

    Returns:
        True if any segment is a credential-shaped name.
    """
    return any(is_secret_name(str(part)) for part in loc)


def redact_input(value: Any) -> Any:
    """Return a copy of a rejected input with credential-keyed entries masked.

    Pydantic reports the *containing object* as the input of a `missing`
    error, so a request that supplies `password` but omits `email`
    produces an error on `email` whose input holds the password. Dict
    values under credential-shaped keys are therefore replaced with
    `REDACTED`, recursing through nested dicts, lists and tuples. List
    and tuple items are checked under their parent's key by the caller's
    location check, not here. The input is never mutated.

    Args:
        value: The `input` of one Pydantic error.

    Returns:
        A structurally similar value that is safe to stringify.
    """
    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_secret_name(str(key)) else redact_input(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_input(item) for item in value]
    return value


def safe_input_text(loc: Iterable[str | int], value: Any) -> str:
    """Render a rejected input as text that cannot carry a credential.

    Args:
        loc: The `loc` tuple of the Pydantic error the input belongs to.
        value: The error's `input`.

    Returns:
        `REDACTED` when the location is credential-shaped; otherwise
        `str()` of the input with any credential-keyed entries masked.
    """
    if is_secret_location(loc):
        return REDACTED
    return str(redact_input(value))
