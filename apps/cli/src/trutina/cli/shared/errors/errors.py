from dataclasses import dataclass

from trutina.shared.errors import ErrorCode


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """Represents a user-facing validation error message.

    Attributes:
        code: Stable machine-readable error identifier.
        message: Human-readable explanation of the validation failure.
    """

    code: ErrorCode
    message: str


type ErrorMap = dict[str, ErrorDetail]
"""
Maps a validation error type to its user-facing metadata.

The key is the Pydantic error type string or custom domain error
identifier raised by the validator. The value is the ErrorDetail
describing the failure.

Keying by error type rather than field name means this map remains
valid as the domain model evolves. Dynamic field paths such as
``lines.0.account`` or ``lines.3.credit_amount`` resolve to the same
error type regardless of their position, so no updates to this map
are required when the model structure changes.

Every member of ``ErrorCode`` must have an entry here -- this is
verified by ``cli/constants/tests/test_errors.py``.
"""
ERRORS: ErrorMap = {
    #
    # Generic validation
    #
    ErrorCode.UNKNOWN_ERROR: ErrorDetail(
        code=ErrorCode.UNKNOWN_ERROR,
        message="An unexpected validation error occurred.",
    ),
    ErrorCode.VALIDATION_ERROR: ErrorDetail(
        code=ErrorCode.VALIDATION_ERROR,
        message="One or more fields failed validation.",
    ),
    ErrorCode.REQUIRED_FIELD: ErrorDetail(
        code=ErrorCode.REQUIRED_FIELD,
        message="This field is required.",
    ),
    ErrorCode.INVALID_NUMBER: ErrorDetail(
        code=ErrorCode.INVALID_NUMBER,
        message="The journal number must be a valid number.",
    ),
    ErrorCode.INVALID_DECIMAL: ErrorDetail(
        code=ErrorCode.INVALID_DECIMAL,
        message="A valid decimal amount is required.",
    ),
    ErrorCode.STRING_TYPE: ErrorDetail(
        code=ErrorCode.STRING_TYPE,
        message="This field must be text.",
    ),
    ErrorCode.STRING_TOO_SHORT: ErrorDetail(
        code=ErrorCode.STRING_TOO_SHORT,
        message="The value is too short.",
    ),
    ErrorCode.STRING_TOO_LONG: ErrorDetail(
        code=ErrorCode.STRING_TOO_LONG,
        message="The value exceeds the allowed length.",
    ),
    ErrorCode.TOO_SHORT: ErrorDetail(
        code=ErrorCode.TOO_SHORT,
        message="The list does not meet the minimum required length.",
    ),
    ErrorCode.TOO_LONG: ErrorDetail(
        code=ErrorCode.TOO_LONG,
        message="The list exceeds the maximum allowed length.",
    ),
    ErrorCode.GREATER_THAN: ErrorDetail(
        code=ErrorCode.GREATER_THAN,
        message="The value is below the minimum allowed value.",
    ),
    ErrorCode.GREATER_THAN_EQUAL: ErrorDetail(
        code=ErrorCode.GREATER_THAN_EQUAL,
        message="The value must be at or above the minimum allowed value.",
    ),
    ErrorCode.LESS_THAN_EQUAL: ErrorDetail(
        code=ErrorCode.LESS_THAN_EQUAL,
        message="The value exceeds the allowed limit.",
    ),
    #
    # Posting date
    #
    ErrorCode.FUTURE_DATE: ErrorDetail(
        code=ErrorCode.FUTURE_DATE,
        message="The posting date cannot be in the future.",
    ),
    ErrorCode.PAST_DATE: ErrorDetail(
        code=ErrorCode.PAST_DATE,
        message="The posting date is outside the supported accounting period.",
    ),
    #
    # Account domain
    #
    ErrorCode.INVALID_ACCOUNT_NAME: ErrorDetail(
        code=ErrorCode.INVALID_ACCOUNT_NAME,
        message=(
            "Account names must start with a letter and may otherwise contain "
            "only letters, digits, spaces, and single separators (& - ' . /) "
            "between words."
        ),
    ),
    ErrorCode.INVALID_ACCOUNT_CODE: ErrorDetail(
        code=ErrorCode.INVALID_ACCOUNT_CODE,
        message="Account codes must be 4 to 6 digits, with no letters, spaces, or symbols.",
    ),
    ErrorCode.UNKNOWN_ACCOUNT: ErrorDetail(
        code=ErrorCode.UNKNOWN_ACCOUNT,
        message="The referenced account does not exist in the chart of accounts.",
    ),
    ErrorCode.DUPLICATE_ACCOUNT_CODE: ErrorDetail(
        code=ErrorCode.DUPLICATE_ACCOUNT_CODE,
        message="An account with this code already exists.",
    ),
    ErrorCode.DUPLICATE_ACCOUNT_NAME: ErrorDetail(
        code=ErrorCode.DUPLICATE_ACCOUNT_NAME,
        message="An account with this name already exists.",
    ),
    ErrorCode.ACCOUNT_HAS_POSTINGS: ErrorDetail(
        code=ErrorCode.ACCOUNT_HAS_POSTINGS,
        message="This account cannot be removed because it has ledger postings.",
    ),
    #
    # Journal domain
    #
    ErrorCode.INVALID_LINE_AMOUNTS: ErrorDetail(
        code=ErrorCode.INVALID_LINE_AMOUNTS,
        message=(
            "A journal line must contain either a debit amount or a credit amount, "
            "not both and not neither."
        ),
    ),
    ErrorCode.UNBALANCED_ENTRY: ErrorDetail(
        code=ErrorCode.UNBALANCED_ENTRY,
        message="The journal entry is not balanced. Total debits must equal total credits.",
    ),
    ErrorCode.UNKNOWN_JOURNAL_ENTRY: ErrorDetail(
        code=ErrorCode.UNKNOWN_JOURNAL_ENTRY,
        message="No journal entry exists with that journal number.",
    ),
    ErrorCode.DUPLICATE_JOURNAL_NUMBER: ErrorDetail(
        code=ErrorCode.DUPLICATE_JOURNAL_NUMBER,
        message="A journal entry with this journal number already exists.",
    ),
    #
    # Posting domain
    #
    ErrorCode.JOURNAL_ALREADY_POSTED: ErrorDetail(
        code=ErrorCode.JOURNAL_ALREADY_POSTED,
        message="This journal entry has already been posted to the ledger.",
    ),
    #
    # User domain
    #
    ErrorCode.DUPLICATE_USER_EMAIL: ErrorDetail(
        code=ErrorCode.DUPLICATE_USER_EMAIL,
        message="A user with this email already exists.",
    ),
    ErrorCode.UNKNOWN_USER: ErrorDetail(
        code=ErrorCode.UNKNOWN_USER,
        message="No user exists with that identifier.",
    ),
    #
    # Storage
    #
    ErrorCode.STORAGE_UNAVAILABLE: ErrorDetail(
        code=ErrorCode.STORAGE_UNAVAILABLE,
        message="The database could not be reached.",
    ),
    ErrorCode.STORAGE_TIMEOUT: ErrorDetail(
        code=ErrorCode.STORAGE_TIMEOUT,
        message="The database did not respond in time.",
    ),
}
