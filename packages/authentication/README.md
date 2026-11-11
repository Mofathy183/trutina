# trutina-authentication

> Identity and authentication contracts for Trutina: ports and models,
> with an Argon2id password hasher, a SHA-256 session-token hasher, a service-only session service and PostgreSQL user,
> login-attempt and session stores as the implementations so far.

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
and what a user, session or login-attempt store must provide. It contains contracts and models, plus `Argon2PasswordHasher` and three
service-only use cases, `RegistrationService`, `PasswordAuthenticator` and `ThrottledAuthenticator`, plus the service-only `SessionService` and
`Sha256SessionTokenHasher`. There is no route or command, and nothing outside tests uses the hasher or any of the use cases yet.
The storage implementations are `PostgresUserRepo`, `PostgresLoginAttemptRepo` and `PostgresSessionRepo` in `trutina-storage-postgres`,
the only workspace package that depends on this one; no app does. Its dependencies are `pydantic` and `argon2-cffi` and `trutina-shared`.
See [CONTEXT.md](CONTEXT.md) for why it is shaped this way and which contracts are provisional.

## API at a Glance

| Symbol                                              | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Identity`                                          | Frozen authenticated principal: just `subject_id`.                                                                                                                                                                                                                                                                                                                                                                                                          |
| `AccessState`                                       | What is checked on every write: `is_active`.                                                                                                                                                                                                                                                                                                                                                                                                                |
| `UserStatusChecker`                                 | Reads a user's `AccessState`; unknown users are inactive.                                                                                                                                                                                                                                                                                                                                                                                                   |
| `Clock`                                             | Source of timezone-aware UTC time.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `AuthEvent` / `AuthEventSink` / `NoOpAuthEventSink` | Secret-free structured events and their receiver.                                                                                                                                                                                                                                                                                                                                                                                                           |
| `PasswordHasher`                                    | Async hash, verify and rehash-check for passwords.                                                                                                                                                                                                                                                                                                                                                                                                          |
| `Argon2PasswordHasher`                              | Argon2id `PasswordHasher`. Hashing and verifying run on worker threads, with a bound on concurrent work. Cost parameters are constructor arguments.                                                                                                                                                                                                                                                                                                         |
| `SessionTokenHasher`                                | Deterministic hash for storing and looking up session tokens, separate from password hashing. `Sha256SessionTokenHasher` implements it.                                                                                                                                                                                                                                                                                                                     |
| `ClientKind`                                        | The two kinds of client a session is issued to, `api` and `cli`. A session is valid only for its kind.                                                                                                                                                                                                                                                                                                                                                      |
| `SessionRecord` / `ValidSession`                    | The stored session (token hash excluded from `repr`) and the result of validating one: the record plus the user's `AccessState`.                                                                                                                                                                                                                                                                                                                            |
| `SessionRepo`                                       | Frozen session persistence contract: create, `get_valid` (kind required, miss is `None`), `touch`, `mark_reauthenticated`, `revoke`, `revoke_all_for_user`, `purge_before`. `PostgresSessionRepo` in `trutina-storage-postgres` implements it; `SessionService` uses it.                                                                                                                                                                                    |
| `User` / `UserRepo`                                 | Minimal user model (email always stored normalized) and its persistence contract: create, lookup by id and email, password-hash update, `set_active`.                                                                                                                                                                                                                                                                                                       |
| `normalize_email`                                   | Canonical stored form of an email: trimmed, then case-folded. Normalization only, no format validation.                                                                                                                                                                                                                                                                                                                                                     |
| `normalize_password`                                | The exact string hashed and verified for a password: converted to NFKC, then leading and trailing whitespace removed (whitespace between characters is kept). Registration and login both call it, so the two always agree.                                                                                                                                                                                                                                 |
| `MAX_PASSWORD_LENGTH`                               | Longest raw password an entry point may accept (128 characters). Checked on the input as typed, before `normalize_password`.                                                                                                                                                                                                                                                                                                                                |
| `MAX_EMAIL_LENGTH`                                  | Longest normalized email accepted at an entry point (254 characters).                                                                                                                                                                                                                                                                                                                                                                                       |
| `RegistrationService`                               | Service-only use case: validates an email and password, rejects a duplicate address, hashes the password and stores an active user. Takes a repo, hasher, clock and optional event sink.                                                                                                                                                                                                                                                                    |
| `RegisterInput` / `RegisteredUser`                  | The registration input (email, `SecretStr` password) and its result (id and stored email only, never the hash).                                                                                                                                                                                                                                                                                                                                             |
| `LoginAttemptRepo`                                  | Failed-login tracking for throttling, keyed on IP and normalized email. Frozen in M2.4; `PostgresLoginAttemptRepo` implements it. Used by `ThrottledAuthenticator`.                                                                                                                                                                                                                                                                                         |
| `Authenticator`                                     | Contract: email and password in, `Identity` out.                                                                                                                                                                                                                                                                                                                                                                                                            |
| `PasswordAuthenticator`                             | Password login. Unknown email, wrong password, disabled account, blank password and over-limit input all raise one `AUTH_INVALID_CREDENTIALS` with an empty context. Verifies against a dummy hash for an unknown email, applies `normalize_password`, rehashes a stale hash after success. Does not throttle and does not use `client_ip`; wrap it in `ThrottledAuthenticator`. Build it with `await PasswordAuthenticator.create(users=..., hasher=...)`. |
| `ThrottledAuthenticator`                            | Wraps any `Authenticator`. Counts failed logins per client IP and normalized email in a sliding window and raises `AUTH_THROTTLED` (with `retry_after_seconds`) at the limit, before any lookup or hashing. Throttles, never locks. Takes the inner authenticator, a `LoginAttemptRepo`, a `Clock`, `max_failures`, `window_seconds` and an optional event sink.                                                                                            |
| `Sha256SessionTokenHasher`                          | Hex SHA-256 of the UTF-8 token, no salt and no pepper. Used by `SessionService` to store and look up tokens.                                                                                                                                                                                                                                                                                                                                                |
| `SessionService`                                    | Service-only use case: `login` (after the authenticator succeeds), `validate`, `logout`, `reauthenticate`, `require_recent_auth`, `revoke_all_for_user`. Takes a session repo, user repo, `Authenticator`, token hasher, clock, a `SessionLifetime` per `ClientKind`, `touch_interval`, `reauth_window`, `purge_retention` and an optional event sink. Every bad token raises one `AUTH_TOKEN_INVALID` with an empty context.                               |
| `IssuedSession` / `SessionLifetime`                 | The login result (the raw token in a `SecretStr`, once, plus subject, kind and absolute expiry) and the idle and absolute lifetime of one client kind.                                                                                                                                                                                                                                                                                                      |

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

Implementations of the repository contracts belong in a storage package;
`UserRepo`, `LoginAttemptRepo` and `SessionRepo` have one each (`PostgresUserRepo`, `PostgresLoginAttemptRepo`, `PostgresSessionRepo`).
password hasher is implemented here by Argon2PasswordHasher; `SessionTokenHasher` has no implementation yet.

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

Register a user (the repository, hasher and clock come from the composition root):

```python
from pydantic import SecretStr
from trutina.authentication import RegisterInput, RegistrationService

service = RegistrationService(users=user_repo, hasher=hasher, clock=clock)
registered = await service.register(
    RegisterInput(email=" Ann@Example.com ", password=SecretStr("correct horse 1"))
)
assert registered.email == "ann@example.com"
```

Verify a login (the repository and hasher come from the composition root):

```python
from pydantic import SecretStr
from trutina.authentication import PasswordAuthenticator

authenticator = await PasswordAuthenticator.create(users=user_repo, hasher=hasher)
identity = await authenticator.authenticate(
    email=" Ann@Example.com ",
    password=SecretStr("correct horse 1"),
    client_ip=None,
)
```

Throttle repeated failures around it (limits normally come from `AuthSettings`):

```python
from trutina.authentication import ThrottledAuthenticator

throttled = ThrottledAuthenticator(
    inner=authenticator,
    attempts=login_attempt_repo,
    clock=clock,
    max_failures=5,
    window_seconds=900,
)
identity = await throttled.authenticate(
    email="ann@example.com",
    password=SecretStr("correct horse 1"),
    client_ip="203.0.113.7",
)
```

## Testing

```bash
uv run pytest -m "unit and authentication"
```

## Sessions

Open, validate and end sessions (the repositories, hasher and clock come from the composition root; pass a `ThrottledAuthenticator` as the authenticator so login and re-authentication are both throttled):

```python
from datetime import timedelta

from pydantic import SecretStr
from trutina.authentication import (
    ClientKind,
    SessionLifetime,
    SessionService,
    Sha256SessionTokenHasher,
)

service = SessionService(
    sessions=session_repo,
    users=user_repo,
    authenticator=throttled,
    hasher=Sha256SessionTokenHasher(),
    clock=clock,
    lifetimes={
        ClientKind.API: SessionLifetime(
            idle=timedelta(hours=24), absolute=timedelta(days=7)
        ),
        ClientKind.CLI: SessionLifetime(
            idle=timedelta(days=14), absolute=timedelta(days=30)
        ),
    },
    touch_interval=timedelta(minutes=5),
    reauth_window=timedelta(minutes=30),
    purge_retention=timedelta(days=7),
)
issued = await service.login(
    email="ann@example.com",
    password=SecretStr("correct horse 1"),
    client_ip="203.0.113.7",
    client_kind=ClientKind.API,
)
valid = await service.validate(issued.token, client_kind=ClientKind.API)
service.require_recent_auth(valid)
```

## See Also

- [CONTEXT.md](CONTEXT.md) — design rationale, provisional contracts, known gaps.
- [`trutina-core`](../core/README.md) — the accounting domain; it never imports this package.
- [`trutina-storage-postgres`](../storage-postgres/README.md) — the `UserRepo`, `LoginAttemptRepo` and `SessionRepo` adapters.
