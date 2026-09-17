# trutina-shared — Context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

Trutina is organized as a workspace of independent packages (`core`, `cli`,
`api`, `storage-mongo`, `storage-postgres`, and others), each of which needs two things that
must behave identically everywhere they're used: a handful of
accounting-adjacent normalization/validation rules that don't belong to any
single feature (account name cleaning, lookup-key folding, single-sided line
amount checking), and one stable, presentation-free error vocabulary that
every layer can raise into and every adapter can catch out of.

Without a shared package, every consuming package would either duplicate
these rules (and drift out of sync) or depend directly on `core`'s internal
schema modules just to reach a validation helper — coupling adapters to
domain internals they have no business knowing about.

`trutina-shared` is deliberately the _lowest_ dependency in the workspace.
Everything can depend on it; it depends on nothing Trutina-specific. In
practice today only `trutina-core` and `trutina-storage-mongo` and `trutina-storage-postgres` list it as a
direct dependency in their own `pyproject.toml` — every other package or app
reaches it transitively through one of those two, and `trutina-config`
reaches it not at all, since configuration parsing has no accounting
meaning to share.

## Design Decisions and Trade-offs

### Error identity lives in `ErrorCode`, not exception subclasses

**Decision:** A single `AppError` (plus its `ValidationAppError` subclass)
carries a `code: ErrorCode` field, rather than the codebase defining a
distinct exception subclass per failure (`DuplicateAccountCodeError`,
`UnbalancedEntryError`, etc.).

**Why:** Adapters (CLI, API) need to `catch` a small, closed set of
exception types and then `switch` on a much larger, open set of failure
identities. An `isinstance` hierarchy for every failure would force every
adapter's `except` chain to grow every time a new failure condition is
added anywhere in the system. Keeping the exception surface at two types
(`AppError`, `ValidationAppError`) and pushing identity into `ErrorCode`
means adapters only ever need `except (ValidationAppError, AppError)`
(subclass order matters — see below) and a dictionary lookup keyed by code.

**Trade-off accepted:** Callers lose Python's native
"different exception type → different `except` clause" ergonomics. This is
intentional — each adapter's own error catalog is the actual dispatch
mechanism, not `except` clauses.

### `AppError` is the only exception type permitted to cross a service boundary

**Invariant — must never be broken:** No package outside `shared` should let
a raw `pydantic.ValidationError`, a driver-specific exception (PyMongo,
etc.), or any other framework exception escape a service method. Everything
crossing a service boundary is `AppError` or `ValidationAppError`.

**Why:** This is what makes every adapter's error-handling code uniform and
independent of which storage driver or validation framework the domain
happens to use underneath. It is also why `shared/errors/translators.py`
exists — Pydantic-specific exception shapes are absorbed _inside_ this
package, one layer below the service boundary, rather than at every call
site that happens to invoke `.model_validate(...)`.

### `AppError.context` is frozen and JSON-primitive-only

**Decision:** `context: Mapping[str, str]` is copied into a `MappingProxyType`
at construction (`__post_init__`), and the type signature restricts it to
string values.

**Why:** `AppError` instances are expected to flow into logging, structured
error responses, and CLI panel rendering. If `context` could hold arbitrary
domain objects (a `ChartOfAccounts`, a Pydantic model), every consumer of
`AppError` would need to know how to serialize arbitrary domain types, and a
careless caller could leak an entire in-memory object graph into a log line
or an HTTP response body. Restricting `context` to JSON-primitive strings
makes every `AppError` safe to serialize by construction, with no
consumer-side judgment calls required.

**Constraint for contributors:** Never widen `context`'s type to accept
non-primitive values, and never stuff a domain object, DTO, or Pydantic
model into it — stringify first, at the raise site.

### `pydantic_error()` carries no message

**Decision:** `pydantic_error(code)` returns a `PydanticCustomError` with an
empty message string.

**Why:** User-facing message text is resolved later, at the adapter layer,
from `ErrorCode` — each presentation layer (CLI, and eventually API) owns
its own catalog. If `pydantic_error()` embedded message text, that text
would either leak into the domain layer (violating the "shared carries no
presentation strings" rule) or be silently overridden downstream, making it
dead weight. Keeping the message empty makes it obvious that `ErrorCode` is
the entire contract — there's no secondary string to accidentally rely on.

### `account_lookup_key` uses `casefold()`, not `lower()`

**Decision:** Case-insensitive account matching uses `str.casefold()`.

**Why:** `casefold()` is the Unicode-correct choice for caseless matching —
it correctly folds characters like German `ß` to `ss`, which `lower()` does
not. Since account names are free-text and Trutina doesn't restrict input
to ASCII, `lower()` would silently under-match on non-ASCII names. This is
a one-line difference that is easy to "fix" back to `lower()` during a
refactor without realizing it's a regression — hence calling it out here as
an invariant, not an implementation detail. `packages/shared/tests/test_rule.py`
exercises this directly (`"Straße"` → `"strasse"`), so a regression here
should fail loudly.

## Known Gaps

`get_field_violations()` currently maps only the Pydantic-native error
types listed in `PYDANTIC_CODES` (`missing`, `int_parsing`,
`decimal_parsing`, `string_type`, `string_too_short`, `string_too_long`,
`too_short`, `too_long`, `greater_than`, `greater_than_equal`,
`less_than_equal`) straight through to their matching `ErrorCode`. A domain
code raised via `pydantic_error(ErrorCode.INVALID_ACCOUNT_NAME)` produces a
Pydantic error `type` of `"account.invalid_name"`, which is not in that
set, so it downgrades to `ErrorCode.UNKNOWN_ERROR` on
`FieldViolation.code`. The original code survives only as a string in
`FieldViolation.value`.

This is easy to mistake for intended design ("domain codes are
deliberately generic at the translation boundary") when it is actually an
unresolved gap — code that wants to react to `ErrorCode.INVALID_ACCOUNT_NAME`
specifically has to read `violation.value`, not `violation.code`, which is
surprising and undocumented at the call site. Anyone extending
`PYDANTIC_CODES` or `get_field_violations()` should treat closing this gap
(making domain codes pass through as themselves) as the natural fix — but
until that lands, downstream code and tests must assert the current
behavior, not the intended one. `test_translators.py` pins this behavior
explicitly (`test_downgrades_domain_error_codes_to_unknown_error`,
`test_preserves_raw_domain_code_in_value_when_downgraded`), so a fix here
is a deliberate, test-visible change, not an accidental one.

Separately, `util.default_posting_date()` exists but is not wired into any
current workflow. This is deferred, not broken — nothing currently calls
it, so it carries no behavioral risk, but it also should not be assumed to
back any current default-date behavior in journal or posting creation.

## Allowed and Forbidden Dependencies

**Allowed (this package may depend on):**

- `pydantic`, `pydantic_core` — the only third-party dependencies.
- The Python standard library.

**Forbidden (this package must never depend on):**

- `trutina.core`, `trutina.cli`, `trutina.api`, `trutina-storage-postgres`, `trutina.storage_mongo`,
  `trutina.config`, or any other workspace package. `shared` sits below all
  of them; if a helper here ever needs something from one of those
  packages, the helper is in the wrong package.
- `typer`, `rich`, `fastapi`, `pymongo`, `beanie`, or any presentation or
  storage-driver library. `shared` has no I/O and no terminal/HTTP
  awareness.

**Direction:** every other workspace package may depend on `trutina-shared`,
directly or transitively. `trutina-shared` depends on nothing
Trutina-specific. This is enforced structurally today (nothing in this
package imports a sibling package); there is no import-linter contract
scoped to `trutina.shared` specifically in the root `pyproject.toml` today —
only `trutina.core` has dedicated `layers`/`forbidden` contracts. `shared`
is a natural candidate for the same treatment if the workspace's
import-linter configuration is extended.

## Control Flow

This package is called, not calling. There is no control flow _within_
`shared` beyond straightforward function calls:

```txt
domain schema validator
  → shared.rule.clean_account_name() / is_valid_line_amounts()
  → (on failure) shared.errors.pydantic_error(code)
  → raised as part of the schema's normal pydantic.ValidationError

service layer
  → catches pydantic.ValidationError
  → shared.errors.ValidationAppError.validation(exc)
  → shared.errors.translators.get_field_violations(exc)   [internal]
  → raises ValidationAppError across the service boundary

adapter (CLI, future API)
  → catches ValidationAppError / AppError
  → looks up ErrorCode in its own presentation catalog
  → renders
```

`shared` never initiates a call into any other package.

## Data Flow

- **Into `rule.py` functions:** raw strings and `Decimal` amounts from
  domain schema fields being validated.
- **Out of `rule.py` functions:** normalized strings, lookup keys, or
  booleans — never a partially-constructed domain object.
- **Into `pydantic_error()`:** an `ErrorCode` member only.
- **Out of `get_field_violations()`:** `list[FieldViolation]`, ordered by
  the order Pydantic itself reports errors (field-declaration order for a
  single model; dotted paths for nested models, e.g. `"children.0.name"`).
- **`FieldViolation.value` is always a string**, even when the underlying
  invalid input was a `Decimal`, `int`, or other type — this is intentional
  (see README) so adapters never need to type-check a violation's value
  before rendering it.

## Extension Points

- **`rule.py`**: add a new module-level function following the existing
  signature style (plain input types in, primitive/`None` out, full
  docstring naming the accounting fact it protects). Do not add a class or
  introduce state — every function here is expected to be pure.
- **`codes.py`**: add new `ErrorCode` members inside the correct grouped
  section (Generic, Pydantic built-in types, Shared date rules, Account,
  Journal, Posting, Storage), using the `"domain.specific_name"`
  string-value convention already established (e.g.
  `"account.invalid_name"`, `"journal.unbalanced"`). Never reuse an
  existing value for a different meaning — `ErrorCode` values are a stable
  cross-package contract; adapters and possibly external clients may key
  off the literal string.
- **`errors.py`**: add a new `AppError` classmethod constructor only when an
  existing one (`not_found`, `conflict`, `storage_unavailable`,
  `storage_timeout`, `unknown`) doesn't already fit the shape of the new
  failure. Keep every new constructor's `context` JSON-primitive-only.
- **`translators.py`**: extend `PYDANTIC_CODES` only when adding support for
  a genuinely new Pydantic-native error type that should pass through
  as-is. Do not use this set as a workaround for the `UNKNOWN_ERROR`
  downgrade issue described above — that requires a real design decision
  about how domain codes should survive translation, not a one-line
  allow-list addition.

## Assumptions This Package Relies On

- Every domain schema that wants a stable `ErrorCode` on validation failure
  raises it via `pydantic_error()` inside a Pydantic validator — not via a
  bare `ValueError` or a hand-rolled exception, both of which would bypass
  `get_field_violations()`'s translation entirely and produce an untyped
  Pydantic error.
- Callers treat `AppError`/`ValidationAppError` as immutable after
  construction (`frozen=True` on both dataclasses) — no code anywhere
  should attempt to mutate `.context` or `.errors` post-construction; both
  are enforced read-only where feasible (`context` via `MappingProxyType`).
- `ErrorCode` string values are treated as a stable public contract once
  shipped — renaming or repurposing an existing value is a breaking change
  for every adapter's presentation catalog, not a local refactor.

## Common Mistakes to Avoid

- **Adding presentation text here.** If you find yourself wanting to add a
  `message` field or a user-facing string anywhere in `shared/errors/`,
  stop — that belongs in the adapter's own catalog, not in the shared error
  model.
- **Assuming `FieldViolation.code` reflects the real domain error.** As
  documented above, it currently doesn't for domain-raised codes — check
  `.value` when the real code matters, and don't write a test that assumes
  the "obviously correct" behavior without checking `translators.py`
  first.
- **Reaching for `str.lower()` instead of `account_lookup_key()`.** Any new
  code that needs case-insensitive account matching should call
  `account_lookup_key()`, not reimplement folding inline — the Unicode
  correctness is the entire point of the helper existing.
- **Putting a feature-specific rule here "because it might be reused
  later."** Speculative generality is a cost, not a hedge. A rule belongs
  in `shared/rule.py` only once at least two features actually use it.
