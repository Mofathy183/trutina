"""
Stable machine-readable identifiers for all domain and infrastructure failures.

ErrorCode values are the shared vocabulary between the service layer and adapters.
Adapters the service output contract map these codes to messages, hints, and status codes.
The domain never carries presentation strings; ErrorCode is the entire contract.

Used by AppError, ValidationAppError, and FieldViolation to
communicate failures across service boundaries.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable identifiers for all application-level failure conditions.

    Error codes are the machine-readable contract exchanged between
    domain logic, services, repositories, and adapters. Codes remain
    stable even when user-facing messages, hints, or presentation
    formats change.

    Every AppError and ValidationAppError must carry an ErrorCode.
    """

    # ── Generic ────────────────────────────────────────────────────────────
    UNKNOWN_ERROR = "error.unknown"
    VALIDATION_ERROR = "error.validation"
    REQUEST_VALIDATION_ERROR = "request.invalid"

    # ── Pydantic built-in types ──────────────
    REQUIRED_FIELD = "missing"
    INVALID_NUMBER = "int_parsing"
    INVALID_DECIMAL = "decimal_parsing"
    STRING_TYPE = "string_type"
    STRING_TOO_SHORT = "string_too_short"
    STRING_TOO_LONG = "string_too_long"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    GREATER_THAN = "greater_than"
    GREATER_THAN_EQUAL = "greater_than_equal"
    LESS_THAN_EQUAL = "less_than_equal"

    # ── Shared date rules ──────────────────────────────────────────────────
    FUTURE_DATE = "date.future"
    PAST_DATE = "date.past"

    # ── Account domain ─────────────────────────────────────────────────────
    INVALID_ACCOUNT_NAME = "account.invalid_name"
    INVALID_ACCOUNT_CODE = "account.invalid_code"
    UNKNOWN_ACCOUNT = "account.unknown"
    DUPLICATE_ACCOUNT_CODE = "account.duplicate_code"
    DUPLICATE_ACCOUNT_NAME = "account.duplicate_name"
    ACCOUNT_HAS_POSTINGS = "account.has_postings"

    # ── Journal domain ─────────────────────────────────────────────────────
    INVALID_LINE_AMOUNTS = "journal.invalid_line_amounts"
    UNBALANCED_ENTRY = "journal.unbalanced"
    UNKNOWN_JOURNAL_ENTRY = "journal.unknown_entry"
    DUPLICATE_JOURNAL_NUMBER = "journal.duplicate_number"

    # ── Posting domain ─────────────────────────────────────────────────────
    JOURNAL_ALREADY_POSTED = "posting.already_posted"

    # ── Storage ────────────────────────────────────────────────────────────
    STORAGE_UNAVAILABLE = "storage.unavailable"
    STORAGE_TIMEOUT = "storage.timeout"

    # ── User domain ────────────────────────────────────────────────────────
    DUPLICATE_USER_EMAIL = "user.duplicate_email"
    UNKNOWN_USER = "user.unknown"

    # ── Auth domain ────────────────────────────────────────────────────────
    # AUTH_INVALID_CREDENTIALS covers wrong password, unknown email and a
    # disabled account alike: all three must be indistinguishable to the
    # caller, so there is one code and its context carries no identifier.
    # AUTH_THROTTLED may carry context["retry_after_seconds"], a digits-only
    # string, which an adapter may turn into a Retry-After value.
    AUTH_INVALID_CREDENTIALS = "auth.invalid_credentials"
    AUTH_THROTTLED = "auth.throttled"
