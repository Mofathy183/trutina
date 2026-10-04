# trutina-authentication

> Identity and authentication contracts for Trutina: ports and models only, no implementations yet.

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

`trutina-authentication` (import path `trutina.authentication`) defines the abstract contracts and small models that identity and authentication will be built on: who an authenticated caller is, how passwords and tokens are hashed and verified, and what a user, refresh-token or login-attempt store must provide. It contains **contracts only**. There is no password hasher, no token implementation, no storage adapter and no route or command; no app or storage package depends on it today. Its only dependency is `pydantic`. See [CONTEXT.md](CONTEXT.md) for why it is shaped this way and which contracts are provisional.

## API at a Glance

| Symbol                                              | Purpose                                                                      |
| --------------------------------------------------- | ---------------------------------------------------------------------------- |
| `Identity`                                          | Frozen authenticated principal: just `subject_id`.                           |
| `AccessState`                                       | What is checked on every write: `is_active`.                                 |
| `UserStatusChecker`                                 | Reads a user's `AccessState`; unknown users are inactive.                    |
| `Clock`                                             | Source of timezone-aware UTC time.                                           |
| `AuthEvent` / `AuthEventSink` / `NoOpAuthEventSink` | Secret-free structured events and their receiver.                            |
| `PasswordHasher`                                    | Async hash, verify and rehash-check for passwords.                           |
| `RefreshTokenHasher`                                | Deterministic hash for refresh-token lookup, separate from password hashing. |
| `TokenIssuer` / `TokenVerifier` / `AccessToken`     | Access-token issue and verify. **Provisional.**                              |
| `User` / `UserRepo`                                 | Minimal user model and its persistence contract.                             |
| `RefreshTokenRepo` and its record/result types      | Refresh-token persistence with atomic rotation. **Provisional.**             |
| `LoginAttemptRepo`                                  | Failed-login tracking for throttling. **Provisional.**                       |
| `Authenticator`                                     | Email and password in, `Identity` out.                                       |

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

Implementations of the repository contracts belong in a storage package; implementations of the hashers and token contracts belong in a later milestone of this package. None exist yet.

## Testing

```bash
uv run pytest -m "unit and authentication"
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, provisional contracts, known gaps.
- [`trutina-core`](../core/README.md) — the accounting domain; it never imports this package.
