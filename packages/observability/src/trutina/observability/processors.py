"""structlog processors for Trutina's logging pipeline.

Each processor follows structlog's (logger, method_name, event_dict)
-> event_dict contract. Attached via configure.py's
ProcessorFormatter(foreign_pre_chain=...), so these run identically on
a structlog call and on a plain stdlib logging.getLogger(__name__)
call from any library.
"""

from typing import Any

# Keys matching these markers are redacted entirely -- there is no
# safe partial form of a password, token, or credential to preserve.
_FULL_REDACT_MARKERS = (
    "password",
    "secret",
    "token",
    "authorization",
    "credential",
    "api_key",
)

# Keys matching these markers hold a connection string, not a bare
# secret -- the host/path/db-name portion is useful for debugging, so
# only the embedded credentials (user:pass@) are masked, not the whole
# value. Any string value containing "://" gets the same treatment
# regardless of its key name, since a URI can appear under an
# unmarked key too.
_URI_LIKE_MARKERS = ("uri", "dsn")

_MONETARY_KEYS = frozenset(
    {
        "amount",
        "debit_amount",
        "credit_amount",
        "debit_total",
        "credit_total",
        "balance",
    }
)
_REDACTED = "***REDACTED***"
_RESERVED_KEYS = frozenset(
    {
        "event",
        "level",
        "logger",
        "timestamp",
        "app",
        "correlation_id",
        "error_code",
        "context",
        "exception",
    }
)

_NOISE_KEYS = frozenset({"color_message"})


def drop_noise_keys(logger, method_name, event_dict):
    """Strip framework-internal record attributes outside the log
    contract -- e.g. uvicorn's ANSI-coded color_message, which
    duplicates `event` and is meaningless outside uvicorn's own
    ColourizedFormatter.
    """
    for key in _NOISE_KEYS:
        event_dict.pop(key, None)
    return event_dict


def inject_app(app: str):
    """Return a processor that stamps every record with a fixed app name."""

    def _processor(logger, method_name, event_dict):
        event_dict.setdefault("app", app)
        return event_dict

    return _processor


def _matches_any(key: str, markers: tuple[str, ...]) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in markers)


def _mask_uri_credentials(value: str) -> str:
    """Strip embedded user:pass@ credentials from a URI-shaped string.

    Returns value unchanged if it doesn't actually contain the
    scheme://user:pass@host shape -- this is a safe no-op, not a
    failure, for a value that merely contains "://" without credentials.
    """
    scheme, sep, rest = value.partition("://")
    if not sep:
        return value
    creds, at, host_and_path = rest.partition("@")
    if not at:
        return value
    return f"{scheme}://***:***@{host_and_path}"


def _redact_value(key: str, value: Any) -> Any:
    if _matches_any(key, _FULL_REDACT_MARKERS):
        return _REDACTED
    if isinstance(value, str) and (
        _matches_any(key, _URI_LIKE_MARKERS) or "://" in value
    ):
        return _mask_uri_credentials(value)
    return value


def redact_sensitive(logger, method_name, event_dict):
    """Mask credential-shaped keys and drop monetary keys above DEBUG.

    Applies to both top-level event_dict keys and the nested "context"
    dict every Trutina log call uses for its structured payload.
    """
    level = event_dict.get("level", "info")

    for key in list(event_dict.keys()):
        if key in _RESERVED_KEYS:
            continue
        event_dict[key] = _redact_value(key, event_dict[key])

    context = event_dict.get("context")
    if isinstance(context, dict):
        cleaned: dict[str, Any] = {}
        for key, value in context.items():
            if key in _MONETARY_KEYS and level != "debug":
                continue
            cleaned[key] = _redact_value(key, value)
        event_dict["context"] = cleaned

    return event_dict


def _coerce_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _coerce_value(v) for k, v in value.items()}
    return f"<{type(value).__name__}>"


def coerce_context(logger, method_name, event_dict):
    """Coerce non-JSON-primitive values inside "context" rather than dumping them."""
    context = event_dict.get("context")
    if isinstance(context, dict):
        event_dict["context"] = {k: _coerce_value(v) for k, v in context.items()}
    return event_dict
