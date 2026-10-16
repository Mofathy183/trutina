from trutina.shared.errors import ErrorCode

"""
User-facing resolution hints for validation errors.

This module provides actionable guidance that helps users correct
validation failures. Hints are intentionally kept separate from error
messages so that message copy and resolution guidance can be updated
independently.

Like the error map, hints are keyed by error type rather than field
name. This ensures hints remain valid as the domain model evolves and
dynamic field paths such as ``lines.0.account`` are handled without
any changes to this file.

Every member of ``ErrorCode`` must have an entry here -- this is
verified by ``cli/constants/tests/test_errors.py``.
"""

type HintMap = dict[str, str]
"""
Maps a validation error type to a plain-text resolution hint.

Keys match the error type strings in ``ERRORS`` from. Values are plain text with no
Rich markup. Markup is applied by the formatter at display time.
"""


HINTS: HintMap = {
    #
    # Generic validation
    #
    ErrorCode.UNKNOWN_ERROR: (
        "An unexpected validation error occurred. Check the field value and try again."
    ),
    ErrorCode.VALIDATION_ERROR: "Review each field listed below and correct the indicated issue.",
    ErrorCode.REQUIRED_FIELD: "Provide a value for this field before continuing.",
    ErrorCode.INVALID_NUMBER: (
        "Enter a whole number for the journal entry, "
        "or leave it blank and one will be assigned automatically."
    ),
    ErrorCode.INVALID_DECIMAL: "Enter a monetary amount such as 100 or 100.50.",
    ErrorCode.STRING_TYPE: "Provide a text value for this field.",
    ErrorCode.STRING_TOO_SHORT: "Provide a longer value.",
    ErrorCode.STRING_TOO_LONG: "Shorten the value and try again.",
    ErrorCode.TOO_SHORT: "Provide at least the minimum number of items required.",
    ErrorCode.TOO_LONG: "Remove items until the list meets the maximum allowed length.",
    ErrorCode.GREATER_THAN: "Provide a value that is above the minimum allowed.",
    ErrorCode.GREATER_THAN_EQUAL: (
        "Provide a value that meets or exceeds the minimum allowed."
    ),
    ErrorCode.LESS_THAN_EQUAL: (
        "Provide a value that does not exceed the allowed limit."
    ),
    #
    # Posting date
    #
    ErrorCode.FUTURE_DATE: (
        "Use today's date or a date in the past. "
        "Leave it blank and today's date will be used automatically."
    ),
    ErrorCode.PAST_DATE: (
        "Use a more recent posting date. "
        "Dates before 2020 are outside the supported accounting period."
    ),
    #
    # Account domain
    #
    ErrorCode.INVALID_ACCOUNT_NAME: (
        "Start the name with a letter, and use only letters, digits, spaces, "
        "and single & - ' . / separators between words."
    ),
    ErrorCode.INVALID_ACCOUNT_CODE: (
        "Use only the digits 0-9, between 4 and 6 of them, for example 1001."
    ),
    ErrorCode.UNKNOWN_ACCOUNT: (
        "This account does not exist in the chart of accounts. "
        "Add it to the chart of accounts first, or check for a typo in the name."
    ),
    ErrorCode.DUPLICATE_ACCOUNT_CODE: (
        "Choose a different account code, or update the existing account instead."
    ),
    ErrorCode.DUPLICATE_ACCOUNT_NAME: (
        "Account names must be unique, regardless of case. Choose a different name."
    ),
    ErrorCode.ACCOUNT_HAS_POSTINGS: (
        "Accounts with existing ledger postings cannot be removed."
    ),
    #
    # Journal domain
    #
    ErrorCode.INVALID_LINE_AMOUNTS: (
        "Set either the debit amount or the credit amount to a value "
        "greater than zero. A single line cannot carry both a debit and "
        "a credit, and it cannot carry neither."
    ),
    ErrorCode.UNBALANCED_ENTRY: (
        "Check that the total of all debit amounts equals the total of "
        "all credit amounts across every line in the entry."
    ),
    ErrorCode.UNKNOWN_JOURNAL_ENTRY: (
        "Check the journal number, or list journal entries to find the correct one."
    ),
    ErrorCode.DUPLICATE_JOURNAL_NUMBER: (
        "This indicates a journal-number allocation defect rather than user "
        "input -- retry the operation."
    ),
    #
    # Posting domain
    #
    ErrorCode.JOURNAL_ALREADY_POSTED: (
        "Look up existing postings for this journal entry instead of posting it again."
    ),
    #
    # User domain
    #
    ErrorCode.DUPLICATE_USER_EMAIL: "Use a different email address.",
    ErrorCode.UNKNOWN_USER: "Check the user identifier and try again.",
    #
    # Storage
    #
    ErrorCode.STORAGE_UNAVAILABLE: (
        "Check that the MongoDB server is running and reachable, then try again."
    ),
    ErrorCode.STORAGE_TIMEOUT: (
        "The database took too long to respond. Check connectivity and try again."
    ),
}

FIELD_LABELS: dict[str, str] = {
    ErrorCode.UNBALANCED_ENTRY: "lines (balance)",
    ErrorCode.INVALID_LINE_AMOUNTS: "lines (amounts)",
    ErrorCode.FUTURE_DATE: "posting_date",
    ErrorCode.DUPLICATE_ACCOUNT_CODE: "code",
    ErrorCode.DUPLICATE_ACCOUNT_NAME: "name",
    ErrorCode.UNKNOWN_ACCOUNT: "code",
    ErrorCode.ACCOUNT_HAS_POSTINGS: "code",
    ErrorCode.UNKNOWN_JOURNAL_ENTRY: "journal_number",
    ErrorCode.DUPLICATE_JOURNAL_NUMBER: "journal_number",
    ErrorCode.JOURNAL_ALREADY_POSTED: "journal_number",
    ErrorCode.DUPLICATE_USER_EMAIL: "email",
    ErrorCode.UNKNOWN_USER: "user_id",
}
