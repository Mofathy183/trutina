# trutina-shared

> Reusable validation rules and structured errors shared across the Trutina workspace.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-shared-informational)

## Quick Start

```bash
uv sync --package trutina-shared
uv run --package trutina-shared python -c "from trutina.shared.rule import clean_account_name; print(clean_account_name('  Cash  '))"
```

## What This Is

`trutina-shared` provides reusable account-validation helpers and a machine-readable error contract for Trutina packages. Its import path is `trutina.shared`; import public error types from `trutina.shared.errors` and rules from their defining modules. See [CONTEXT.md](CONTEXT.md) for design rationale, invariants, and known gaps.

## API at a Glance

| Symbol                                          | Purpose                                                                       |
| ----------------------------------------------- | ----------------------------------------------------------------------------- |
| `clean_account_name()`                          | Trims and validates an account name, returning `None` when it is invalid.     |
| `account_lookup_key()`                          | Produces a case-insensitive key for a validated account name.                 |
| `is_valid_line_amounts()`                       | Checks that exactly one of a line's debit and credit amounts is positive.     |
| `ErrorCode`                                     | Stable identifiers for domain and infrastructure failures.                    |
| `AppError`                                      | Structured application exception, including constructors for common failures. |
| `ValidationAppError` and `FieldViolation`       | Error records for one or more invalid fields.                                 |
| `pydantic_error()` and `get_field_violations()` | Bridge Pydantic validation errors to the shared error contract.               |
| `default_posting_date()`                        | Returns today's local date at midnight.                                       |

## Usage

Validate and normalize an account name before using it in a schema:

```python
from trutina.shared.rule import account_lookup_key, clean_account_name

name = clean_account_name("  Accounts Receivable  ")
assert name == "Accounts Receivable"
assert account_lookup_key(name) == "accounts receivable"
```

Check a double-entry line's two amounts:

```python
from decimal import Decimal

from trutina.shared.rule import is_valid_line_amounts

assert is_valid_line_amounts(Decimal("100.00"), Decimal("0"))
```

Create a structured error for an adapter or service boundary:

```python
from trutina.shared.errors import AppError, ErrorCode

error = AppError.not_found(ErrorCode.UNKNOWN_ACCOUNT, "account", "1000")
assert error.context["identifier"] == "1000"
```

## Testing

```bash
uv run pytest -m "unit and shared"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, trade-offs, invariants, and known gaps.
- [`trutina-core`](../core/README.md) — direct workspace consumer of the rules and error contract.
- [`trutina-storage-mongo`](../storage-mongo/README.md) — direct workspace consumer of the error contract.
- [`trutina-storage-postgres`](../storage-postgres/README.md) — direct workspace consumer of the error contract.
