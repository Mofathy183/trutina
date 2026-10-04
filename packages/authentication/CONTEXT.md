# trutina-authentication — Context

For usage, see README.md. This document explains why, not how.

## Why This Package Exists

Trutina needs to know who performed a write, without the accounting domain learning what a user, a password or a token is. This package holds the vocabulary for identity and authentication so that `trutina-core` never has to. Today it is contracts only: it fixes the seams that later milestones fill in, and gives tests fakes to build against before any implementation exists.

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
- `User` is deliberately minimal; the users milestone designs its final shape alongside its adapter.

## Allowed and Forbidden Dependencies

**Allowed:** `pydantic` and the standard library. May also depend on `trutina-shared` and `trutina-config` (the layers below it) if a later change needs them.

**Forbidden:** `trutina.core`; `trutina.storage_mongo`, `trutina.storage_postgres`, `trutina.observability`, `structlog`; `sqlalchemy`, `asyncpg`, `beanie`, `pymongo`, `fastapi`, `starlette`, `typer`, `rich`. Enforced by the workspace import-linter: core and authentication are independent siblings in the layers contract, and dedicated forbidden contracts cover the rest. Like every package outside the two apps, it emits through stdlib `logging` only.

**Direction:** storage packages and the apps may import this package; it imports nothing above `shared`/`config`.

## Known Gaps

- No implementation of any contract exists. No hasher, token module, storage adapter, route or command uses these ports yet, and no app or storage package declares a dependency on this package.
- No `AUTH_*` `ErrorCode` members exist yet. `Authenticator.authenticate` documents that it will raise `AppError` but cannot name a code until the first implementation adds them.
- Once password login ships there is no self-service recovery for a locked-out user until password reset is built (deferred past core authentication).
- `FakeUserRepo.create` does not reject duplicate emails; the service pre-check and the storage unique index are the real guards.

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
