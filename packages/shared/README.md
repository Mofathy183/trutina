# trutina-shared

The lowest-level package in the Trutina workspace: reusable accounting-adjacent validation helpers and the shared domain error model used by every other package.

## What Is This

`trutina-shared` (import path `trutina.shared`) depends on nothing else in the workspace — only `pydantic`. It holds two kinds of code:

- Validation/normalization rules reused by more than one domain schema (e.g. account name normalization).
- The stable error contract (`ErrorCode`, `AppError`, `ValidationAppError`, `FieldViolation`) that every service boundary raises and every adapter translates.

A helper specific to a single feature (accounts, journals, postings) belongs in that feature's own module, not here.

## Installation

Part of the `uv` workspace; not installed standalone.

```bash
uv sync --package trutina-shared
```

Other workspace packages depend on it via `{ workspace = true }` sources, not a version pin.

## Public API

`trutina.shared` itself re-exports nothing (`__init__.py` is empty) — import from the submodules below.

### `trutina.shared.rule`

| Symbol                                                           | Purpose                                                                                                                     |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `clean_account_name(value: str) -> str \| None`                  | Trims and validates an account name against the permitted character set. Returns the trimmed name, or `None` if invalid.    |
| `account_lookup_key(name: str) -> str`                           | Case-insensitive lookup key for an already-validated account name, via `str.casefold()` (not `str.lower()`).                |
| `is_valid_line_amounts(debit: Decimal, credit: Decimal) -> bool` | `True` iff exactly one of `debit`/`credit` is positive (XOR) — a journal line represents exactly one side of a transaction. |

### `trutina.shared.errors`

| Symbol                                                                        | Purpose                                                                                                                                                     |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ErrorCode`                                                                   | `StrEnum` of every stable failure identifier in the system — the only vocabulary adapters switch on.                                                        |
| `AppError`                                                                    | The only exception type permitted to cross a service boundary. Carries `code`, a JSON-primitive-only `context` mapping, and an optional diagnostic `cause`. |
| `ValidationAppError`                                                          | `AppError` subclass carrying `errors: list[FieldViolation]` for multi-field validation failures.                                                            |
| `FieldViolation`                                                              | A single field-level failure: `code`, `field` (dotted path), `value` (stringified).                                                                         |
| `pydantic_error(code: ErrorCode) -> PydanticCustomError`                      | Raise from inside a Pydantic validator to tag a domain failure with a stable `ErrorCode`.                                                                   |
| `get_field_violations(exc: pydantic.ValidationError) -> list[FieldViolation]` | Translates a `pydantic.ValidationError` into `list[FieldViolation]`.                                                                                        |
| `PYDANTIC_CODES`                                                              | Allow-list of Pydantic-native error `type` strings that map directly to an `ErrorCode`; anything else downgrades to `ErrorCode.UNKNOWN_ERROR`.              |

### `trutina.shared.util`

| Symbol                               | Purpose                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `default_posting_date() -> datetime` | Today's date with the time component zeroed. **Not called anywhere in the active workflow today** — present, but nothing wires it in. |

## Usage

Raising a domain validation error from a schema validator:

```python
from pydantic import BaseModel, field_validator
from trutina.shared.errors import ErrorCode, pydantic_error
from trutina.shared.rule import clean_account_name


class Account(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = clean_account_name(value)
        if cleaned is None:
            raise pydantic_error(ErrorCode.INVALID_ACCOUNT_NAME)
        return cleaned
```

Translating a `ValidationError` at a service boundary:

```python
from pydantic import ValidationError
from trutina.shared.errors import ValidationAppError

try:
    Account(name="")
except ValidationError as exc:
    raise ValidationAppError.validation(exc)
```

Constructing service-level errors directly:

```python
from trutina.shared.errors import AppError, ErrorCode

AppError.not_found(ErrorCode.UNKNOWN_ACCOUNT, resource="account", identifier="9999")
AppError.conflict(
    ErrorCode.DUPLICATE_ACCOUNT_CODE,
    resource="account",
    field_name="code",
    value="1000",
)
AppError.storage_unavailable(cause=some_connection_error)
AppError.storage_timeout(cause=some_timeout_error)
AppError.unknown(cause=some_unexpected_error)
```

Normalizing and comparing account names:

```python
from trutina.shared.rule import account_lookup_key, clean_account_name

name = clean_account_name("  Accounts Receivable  ")  # "Accounts Receivable"
key = account_lookup_key(name)  # "accounts receivable"
```

> **Known behavior:** `get_field_violations()` only maps the `PYDANTIC_CODES` allow-list (Pydantic-native error types) to their matching `ErrorCode`. A domain code raised via `pydantic_error(...)` currently downgrades to `ErrorCode.UNKNOWN_ERROR` on `FieldViolation.code` — the original code survives only as a string in `FieldViolation.value`. Code that needs to react to the specific domain code must read `.value`, not `.code`. See `CONTEXT.md`.

## Integration

Direct workspace dependents, per each package's own `pyproject.toml`: `trutina-core` and `trutina-storage-mongo`. Every other consumer (`apps/cli`, `apps/api`) reaches `trutina-shared` only transitively through one of those two. `trutina-config` currently declares **no** dependency on `trutina-shared`.

- Domain schemas import `shared.rule` for normalization and `shared.errors.pydantic_error` to raise `ErrorCode`-backed validation failures.
- Services import `shared.errors` (`AppError`, `ValidationAppError`) — the only exception types permitted to cross a service boundary.
- CLI and API adapters catch `AppError`/`ValidationAppError` and translate `ErrorCode` into their own presentation-layer messages, hints, and status codes; none of that wording lives in this package.
- `trutina.shared` imports nothing from `core`, `cli`, `api`, `infrastructure`, or `config`.

## Extending

- **New reusable validation rule** (used by 2+ domain schemas): add it to `rule.py` as a pure function, documented as the business rule it protects, not the mechanical check.
- **New failure condition**: add a member to `ErrorCode` in `codes.py`, in the appropriate grouped section (Generic, Pydantic built-in types, Shared date rules, Account, Journal, Posting, Storage). Never repurpose an existing value for a different meaning — `ErrorCode` values are a stable cross-package contract.
- **New `AppError` constructor**: add a `classmethod` shaped like `not_found`/`conflict`/`storage_unavailable`; keep `context` JSON-primitive-only.
- **New Pydantic-native type that should pass through translation as-is**: add it to `PYDANTIC_CODES` in `translators.py`. Do not use this as a workaround for the `UNKNOWN_ERROR` downgrade described above — that needs a real design decision, not a one-line addition.
- Do not add CLI, Rich, Typer, FastAPI, or any other presentation-specific logic here.

## Testing

```bash
uv run pytest -m "unit and shared"
```

Tests live under `packages/shared/tests/` (`rule.py` — pure input/output assertions, no mocking) and `packages/shared/src/trutina/shared/errors/tests/` (`errors.py`/`translators.py` — real `pydantic.ValidationError` instances raised from inline models, asserting the specific `ErrorCode` on each `FieldViolation`, not just the exception type). The `shared` layer marker is derived automatically from file path by the root `conftest.py`; only the `unit`/`integration` speed marker needs to be written on the test itself.
