# trutina-authentication — Context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

Trutina needs to know who performed a write, without the accounting domain learning what a user, a password or a token is. This package holds the vocabulary for identity and authentication so that `trutina-core` never has to. Today it is contracts and models only (the one adapter, for `UserRepo`, lives in `trutina-storage-postgres`): it fixes the seams that later milestones fill in, and gives tests fakes to build against before any implementation exists.

## The Rule This Package Protects

`trutina.core` never imports `trutina.authentication`, and no core service method takes an `Identity`. Core sees only an opaque, required, keyword-only `actor: str` on write methods, supplied by the calling API or CLI handler. This package therefore sits beside core, not above or below it.

## Layout

Four small folders group the contracts by what they are for. Every public symbol is re-exported from the package root, so callers always import from `trutina.authentication`, never from a subfolder.

| Folder         | Holds                                                                              | Role                                |
| -------------- | ---------------------------------------------------------------------------------- | ----------------------------------- |
| `identity/`    | `Identity`, `AccessState`, `UserStatusChecker`                                     | Who is acting, and whether they may |
| `credentials/` | `PasswordHasher`, `User`, `UserRepo`, `LoginAttemptRepo`, `Authenticator`          | Checking a login                    |
| `tokens/`      | `access.py` (`AccessToken`, issuer, verifier); `refresh.py` (hasher, record, repo) | Sessions after login                |
| `shared/`      | `Clock`, `AuthEvent`, `AuthEventSink`, `NoOpAuthEventSink`                         | Cross-cutting ports                 |

Internal direction: `credentials` and `tokens` may import `identity`; `identity` and `shared` import nothing from their siblings. This is observed convention, not an import-linter contract. A folder exists only where two or more related modules do; do not create a folder for a single file.

## Design Decisions and Trade-offs

### `Identity` is only a subject id

`Identity` carries `subject_id` and nothing else: no email, no roles. It cannot go stale when a profile changes, and roles arrive with authorization later. It lives in this package rather than its own because one frozen dataclass does not justify a package, a CI lane and a linter layer; split it out only when a second consumer is named.

### `AccessState`, not a boolean

`UserStatusChecker` returns an `AccessState` (today just `is_active`) so that adding a role later extends the same per-write query instead of changing every write path. An unknown user returns `is_active=False`, because callers treat a missing and a disabled user the same.

### Two hashers, never interchangeable

`PasswordHasher` is slow, salted and verified; `RefreshTokenHasher` is fast and deterministic because refresh tokens are 256-bit random values that are looked up by hash. Using the password hasher for lookup is impossible by design (it is not deterministic), and using the fast hash for passwords would be a security defect, so the two are separate ports.

### Email is stored once, normalized by the model

`normalize_email()` trims and case-folds, and `User` applies it in a validator, so every constructed user already carries the canonical address. One plain unique index on one column then gives case-insensitive uniqueness, with no second key column and no database-side `lower()` that could disagree with `casefold()`. `UserRepo.get_by_email` normalizes its argument the same way. The rule lives here, with the model that owns it, not in `trutina-shared`. Cost accepted: the address as typed is not kept. It is normalization only; no email format is validated.

### `created_at` belongs to the database

`UserRepo.create` ignores a caller-supplied `created_at`. The storage layer stamps it and reads it back, so there is one source for the timestamp.

### Deactivation, not deletion, and errors without personal data

Users are never hard-deleted, so `set_active` is how access is removed. `set_active` and `update_password_hash` raise `UNKNOWN_USER` for an unknown id. `create` raises `DUPLICATE_USER_EMAIL` with a context of `resource` and `field` only, never the address, because `AppError.context` reaches logs and responses.

### `PasswordHasher` is async and owns its own offloading

Hashing is CPU-bound. The implementation, not the caller, runs it off the event loop and bounds concurrency, so no call site can forget either. `verify` returns `False` for a malformed hash so the unknown-user path (verifying against a dummy hash) behaves exactly like a wrong password.

### `Clock` returns timezone-aware UTC

Authentication timestamps are always aware. The accounting domain's posting dates are naive; the two must never be compared directly. All expiry and rotation arithmetic takes its time from `Clock`, so it is testable without sleeping.

### `TokenVerifier` returns `Identity | None`

An invalid token is an expected, frequent outcome, not an exceptional one. Returning `None` lets the caller map it to its own 401 and keeps this package free of `ErrorCode` and of any dependency on `trutina-shared` for now.

### Rotation: atomic step in the repo, policy in the service

`RefreshTokenRepo.rotate` is the single atomic operation. It returns `ROTATED`, `REUSED` or `INVALID` plus the presented token's prior record. The grace window for harmless reuse and the decision to revoke a family are service policy, not repository behavior, so a storage adapter holds no authentication rules. The contract requires that of any number of concurrent rotations of one token exactly one returns `ROTATED`.

### Events carry no secrets

`AuthEvent.context` is a frozen string-to-string mapping, the same rule `AppError.context` follows, so an event is safe to log by construction. `AuthEventSink.emit` must never raise.

## Provisional Contracts

These may change before they are implemented:

- `TokenIssuer`, `TokenVerifier`, `AccessToken` and `RefreshTokenRepo` depend on decision D1 (JWT versus one opaque session mechanism), settled in the M3 ADR.
- `LoginAttemptRepo` is finalized in M2 with the throttling logic.
- `User` is deliberately minimal: fields are added by the milestone that needs them.

## Allowed and Forbidden Dependencies

**Allowed:** `pydantic` and the standard library. May also depend on `trutina-shared` and `trutina-config` (the layers below it) if a later change needs them.

**Forbidden:** `trutina.core`; `trutina.storage_postgres`, `trutina.observability`, `structlog`; `sqlalchemy`, `asyncpg`, `fastapi`, `starlette`, `typer`, `rich`. Enforced by the workspace import-linter: core and authentication are independent siblings in the layers contract, and dedicated forbidden contracts cover the rest. Like every package outside the two apps, it emits through stdlib `logging` only.

**Direction:** storage packages and the apps may import this package; it imports nothing above `shared`/`config`.
`trutina-storage-postgres` imports it, forUserRepo.

## Known Gaps

- Only `UserRepo` has an implementation (`PostgresUserRepo`, in `trutina-storage-postgres`, which declares the dependency on this package). No hasher, token module, route or command exists, and no app depends on this package.
- Only two `AUTH_*` `ErrorCode` members exist, `AUTH_INVALID_CREDENTIALS` and `AUTH_THROTTLED`,
  with API and CLI catalog entries, and nothing raises them yet (M2.6, M2.7).
  The token codes and `AUTH_USER_DISABLED` land with M3. The user codes `DUPLICATE_USER_EMAIL` and `UNKNOWN_USER` also exist.
- Once password login ships there is no self-service recovery for a locked-out user until password reset is built (deferred past core authentication).
- `FakeUserRepo.create` does not reject duplicate emails; the service pre-check and the storage unique index are the real guards.
- Email format is not validated, and normalization is a case fold only.
- `DUPLICATE_USER_EMAIL` reveals that an address is registered. Whether it may reach a caller is decided with the register use case.

## Extension Points

- A new contract: add a module to the folder it belongs to, export it from that folder's `__init__.py` and the package root, add a fake under `tests/fakes/auth.py`, and a test beside the code.
- A concrete hasher or token module: add it here, since it needs only cryptographic dependencies and no I/O.
- A storage adapter for a repository contract: implement it in the storage package, not here.

## Common Mistakes to Avoid

- Importing this package from `trutina.core`, or giving a core service an `Identity`.
- Adding storage, web or CLI imports "for convenience".
- Putting policy (grace windows, throttling thresholds, expiry arithmetic) into a repository contract.
- Using naive datetimes with any contract here.
- Logging or putting a password, token, hash or key into an `AuthEvent`.
- Treating a provisional contract as stable in documentation or downstream code.
