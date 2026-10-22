# trutina-authentication

> Identity and authentication contracts for Trutina: ports and models,
> with an Argon2id password hasher and a PostgreSQL user store as the only implementations so far.

![CI](https://github.com/Mofathy183/trutina/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Coverage](https://img.shields.io/badge/coverage-not_wired_up-lightgrey)
![Layer](https://img.shields.io/badge/layer-authentication-informational)

## Quick Start

```bash
uv sync --package trutina-authentication
uv run pytest -m "unit and authentication"
```

## What This Is

`trutina-authentication` (import path `trutina.authentication`) defines the abstract contracts and small models that identity and authentication
will be built on: who an authenticated caller is, how passwords and tokens are hashed and verified,
and what a user, refresh-token or login-attempt store must provide. It contains contracts and models,
plus one concrete implementation, `Argon2PasswordHasher`. There is no token implementation,
no refresh-token hasher and no route or command, and nothing outside tests uses the hasher yet.
The one storage implementation of any contract is `PostgresUserRepo` in `trutina-storage-postgres`,
the only workspace package that depends on this one; no app does. Its dependencies are `pydantic` and `argon2-cffi`.
See [CONTEXT.md](CONTEXT.md) for why it is shaped this way and which contracts are provisional.

## API at a Glance

| Symbol                                              | Purpose                                                                                                                                               |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Identity`                                          | Frozen authenticated principal: just `subject_id`.                                                                                                    |
| `AccessState`                                       | What is checked on every write: `is_active`.                                                                                                          |
| `UserStatusChecker`                                 | Reads a user's `AccessState`; unknown users are inactive.                                                                                             |
| `Clock`                                             | Source of timezone-aware UTC time.                                                                                                                    |
| `AuthEvent` / `AuthEventSink` / `NoOpAuthEventSink` | Secret-free structured events and their receiver.                                                                                                     |
| `PasswordHasher`                                    | Async hash, verify and rehash-check for passwords.                                                                                                    |
| `Argon2PasswordHasher`                              | Argon2id `PasswordHasher`. Hashing and verifying run on worker threads, with a bound on concurrent work. Cost parameters are constructor arguments.   |
| `RefreshTokenHasher`                                | Deterministic hash for refresh-token lookup, separate from password hashing.                                                                          |
| `TokenIssuer` / `TokenVerifier` / `AccessToken`     | Access-token issue and verify. **Provisional.**                                                                                                       |
| `User` / `UserRepo`                                 | Minimal user model (email always stored normalized) and its persistence contract: create, lookup by id and email, password-hash update, `set_active`. |
| `normalize_email`                                   | Canonical stored form of an email: trimmed, then case-folded. Normalization only, no format validation.                                               |
| `RefreshTokenRepo` and its record/result types      | Refresh-token persistence with atomic rotation. **Provisional.**                                                                                      |
| `LoginAttemptRepo`                                  | Failed-login tracking for throttling. **Provisional.**                                                                                                |
| `Authenticator`                                     | Email and password in, `Identity` out.                                                                                                                |

In-memory fakes for these contracts live in the repo's shared test infrastructure (`tests/fakes/auth.py`), not in this package.

## Usage

Report an event and carry an identity:

```python
from uuid import uuid4

from trutina.authentication import AuthEvent, Identity, NoOpAuthEventSink

identity = Identity(subject_id=uuid4())
NoOpAuthEventSink().emit(
    AuthEvent(name="auth.example", context={"subject": str(identity.subject_id)})
)
```

Implementations of the repository contracts belong in a storage package; `UserRepo` has one (`PostgresUserRepo`).
password hasher is implemented here by Argon2PasswordHasher; the refresh-token hasher and the token contracts have no implementation yet.

Hash and verify a password (cost parameters come from the caller, normally `AuthSettings`):

```python
from pydantic import SecretStr
from trutina.authentication import Argon2PasswordHasher

hasher = Argon2PasswordHasher(
    time_cost=3, memory_cost_kib=65536, parallelism=1, max_concurrency=4
)
stored = await hasher.hash(SecretStr("example-password"))
assert await hasher.verify(SecretStr("example-password"), stored)
```

## Testing

```bash
uv run pytest -m "unit and authentication"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, provisional contracts, known gaps.
- [`trutina-core`](../core/README.md) — the accounting domain; it never imports this package.
- [`trutina-storage-postgres`](../storage-postgres/README.md) — the `UserRepo` adapter.
