"""API-owned catalog mapping domain ErrorCode values to HTTP presentation.

Mirrors cli/shared/errors/{errors,hint}.py's combined role for the CLI:
presentation wording, HTTP status selection, and resolution guidance
are an API-layer concern and are kept separate from
trutina.shared.errors so the shared domain error model never carries
HTTP-specific metadata. AppError and ValidationAppError stay a pure,
transport-agnostic contract; this module is the one place that decides
what a given ErrorCode looks like over HTTP.

Every ErrorCode the domain can currently raise has an entry here.
handlers.py falls back to DEFAULT_ERROR_ENTRY for any code missing from
this catalog rather than raising a KeyError mid-request -- a future
ErrorCode added to shared/errors/codes.py without a matching catalog
entry degrades to a generic 500 instead of crashing the handler itself.
"""

from dataclasses import dataclass

from fastapi import status
from trutina.shared.errors import ErrorCode


@dataclass(frozen=True, slots=True)
class ErrorCatalogEntry:
    """Static HTTP presentation for a single ErrorCode.

    Attributes:
        status_code: HTTP status returned whenever this ErrorCode
            surfaces from an AppError or ValidationAppError. Sourced
            from `fastapi.status` rather than raw ints so the catalog
            reads consistently with the rest of the FastAPI codebase.
        message: User-facing summary. May reference AppError.context
            keys via str.format() placeholders (e.g. "{identifier}",
            "{value}"). handlers.py fills these in from the raised
            error's own context; a template is left unfilled (returned
            as-is) if a referenced key is absent, rather than raising.
        hint: Optional resolution guidance -- what the caller should try
            next (e.g. "use a different account code" for a conflict,
            "retry after a short delay" for a storage failure). May
            also reference context placeholders, filled the same way as
            `message`. None when the message is already self-explanatory
            enough that a hint would just restate it (e.g. UNKNOWN_ERROR,
            or the individual Pydantic built-in codes, which only ever
            appear nested inside a ValidationErrorResponse's `details`
            alongside the field they belong to).
    """

    status_code: int
    message: str
    hint: str | None = None


DEFAULT_ERROR_ENTRY = ErrorCatalogEntry(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    message="An unexpected error occurred.",
)


ERROR_CATALOG: dict[ErrorCode, ErrorCatalogEntry] = {
    # ── Generic ──────────────────────────────────────────────────────
    ErrorCode.UNKNOWN_ERROR: DEFAULT_ERROR_ENTRY,
    ErrorCode.VALIDATION_ERROR: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The request failed validation.",
        hint="Review the `details` array for the specific fields that failed.",
    ),
    # ── Pydantic built-in types ──────────────────────────────────────
    # Only ever surfaced as FieldErrorDetail entries inside a
    # ValidationErrorResponse's `details`, never as a standalone
    # top-level error -- so no hint is attached here; the field name in
    # `details` already tells the caller what to fix.
    ErrorCode.REQUIRED_FIELD: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This field is required."
    ),
    ErrorCode.INVALID_NUMBER: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This field must be a valid integer."
    ),
    ErrorCode.INVALID_DECIMAL: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "This field must be a valid decimal number.",
    ),
    ErrorCode.STRING_TYPE: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This field must be a string."
    ),
    ErrorCode.STRING_TOO_SHORT: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This field is too short."
    ),
    ErrorCode.STRING_TOO_LONG: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This field is too long."
    ),
    ErrorCode.TOO_SHORT: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "Too few items were provided."
    ),
    ErrorCode.TOO_LONG: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "Too many items were provided."
    ),
    ErrorCode.GREATER_THAN: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This value is too small."
    ),
    ErrorCode.GREATER_THAN_EQUAL: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This value is too small."
    ),
    ErrorCode.LESS_THAN_EQUAL: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "This value is too large."
    ),
    # ── Shared date rules ────────────────────────────────────────────
    ErrorCode.FUTURE_DATE: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The date cannot be in the future.",
        hint="Use a date on or before today.",
    ),
    ErrorCode.PAST_DATE: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The date is too far in the past.",
        hint="Use a date after the supported accounting period start (2020-01-01).",
    ),
    # ── Account domain ───────────────────────────────────────────────
    ErrorCode.INVALID_ACCOUNT_NAME: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The account name is not valid.",
        hint=(
            "Account names must start with a letter and use only letters, "
            "digits, spaces, and single & - ' . / separators."
        ),
    ),
    ErrorCode.INVALID_ACCOUNT_CODE: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The account code is not valid.",
        hint="Account codes must be 4 to 6 digits (0-9), for example '1001'.",
    ),
    ErrorCode.UNKNOWN_ACCOUNT: ErrorCatalogEntry(
        status.HTTP_404_NOT_FOUND,
        "No account was found for '{identifier}'.",
        hint="Verify the account code or name, or create it first via POST /accounts.",
    ),
    ErrorCode.DUPLICATE_ACCOUNT_CODE: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "An account with code '{value}' already exists.",
        hint="Choose a code other than '{value}', or update the existing account instead.",
    ),
    ErrorCode.DUPLICATE_ACCOUNT_NAME: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "An account named '{value}' already exists.",
        hint="Choose a name other than '{value}', or update the existing account instead.",
    ),
    ErrorCode.ACCOUNT_HAS_POSTINGS: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "This account has existing postings and cannot be removed.",
        hint="Accounts with posting history cannot be deleted.",
    ),
    # ── Journal domain ───────────────────────────────────────────────
    ErrorCode.INVALID_LINE_AMOUNTS: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "A journal line must carry either a debit or a credit amount, not both.",
        hint="Set exactly one of debit_amount/credit_amount to a positive value.",
    ),
    ErrorCode.UNBALANCED_ENTRY: ErrorCatalogEntry(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Total debits must equal total credits.",
        hint="Adjust the journal lines so total debits and total credits match exactly.",
    ),
    ErrorCode.UNKNOWN_JOURNAL_ENTRY: ErrorCatalogEntry(
        status.HTTP_404_NOT_FOUND,
        "No journal entry was found for '{identifier}'.",
        hint="Verify the journal number, or create the entry first via POST /journal-entries.",
    ),
    ErrorCode.DUPLICATE_JOURNAL_NUMBER: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "Journal number '{value}' already exists.",
        hint="Please retry the request.",
    ),
    # ── Posting domain ───────────────────────────────────────────────
    ErrorCode.JOURNAL_ALREADY_POSTED: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "Journal entry '{value}' has already been posted.",
        hint="Each journal entry can only be posted once; fetch its existing postings instead.",
    ),
    # ── User domain ──────────────────────────────────────────────────
    # Neither message interpolates context: DUPLICATE_USER_EMAIL's context
    # never carries the address, and no user identifier belongs in a
    # response body.
    ErrorCode.DUPLICATE_USER_EMAIL: ErrorCatalogEntry(
        status.HTTP_409_CONFLICT,
        "A user with this email already exists.",
        hint="Use a different email address.",
    ),
    ErrorCode.UNKNOWN_USER: ErrorCatalogEntry(
        status.HTTP_404_NOT_FOUND,
        "No user was found.",
        hint="Verify the user identifier.",
    ),
    # ── Auth domain ──────────────────────────────────────────────────
    # No message interpolates context: unknown email, wrong password and
    # a disabled account must produce the same response, and the retry
    # delay travels in the Retry-After header, not the body.
    ErrorCode.AUTH_INVALID_CREDENTIALS: ErrorCatalogEntry(
        status.HTTP_401_UNAUTHORIZED,
        "The email or password is incorrect.",
        hint="Check your email and password and try again.",
    ),
    ErrorCode.AUTH_THROTTLED: ErrorCatalogEntry(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many sign-in attempts.",
        hint="Wait before trying again.",
    ),
    # ── Storage ──────────────────────────────────────────────────────
    ErrorCode.STORAGE_UNAVAILABLE: ErrorCatalogEntry(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The database is currently unavailable.",
        hint="Retry the request after a short delay. Contact support if this persists.",
    ),
    ErrorCode.STORAGE_TIMEOUT: ErrorCatalogEntry(
        status.HTTP_504_GATEWAY_TIMEOUT,
        "The database did not respond in time.",
        hint="Retry the request. Frequent timeouts may indicate database load.",
    ),
}
