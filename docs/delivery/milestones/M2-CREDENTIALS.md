# M2 — Credentials

## Milestone record

### M2 — Password register and login, no tokens

- **M2.0 done** (issue #64, PR #65, merge commit `0ab8974`, 8 of 8 checks green): nested credential redaction in `trutina-observability`. See the M2.0 ticket card
- **M2.1 done** (issue #66, PR #67, merge commit `a348d50`, 8 of 8 checks green): secret-safe validation errors. `get_field_violations()` masks a credential-shaped input before it reaches `FieldViolation.value`, and the API and CLI are proven not to echo it. See the M2.1 ticket card
- **M2.3 done** (issue #68, PR #69, merge commit `919c131`, 8 of 8 checks green): the first `AUTH_*` codes, `AUTH_INVALID_CREDENTIALS` (401) and `AUTH_THROTTLED` (429 with `Retry-After`), with API and CLI catalog entries and parity tests. Nothing raises them until M2.6 and M2.7. See the M2.3 ticket card
- **M2.2 done** (issue #70, branch `feat/70-password-hasher`, CI green; PR number and merge commit not recorded here yet): `Argon2PasswordHasher`, Argon2id through `argon2-cffi`, with four `AuthSettings` fields. Nothing uses it yet. See the M2.2 ticket card
- **M2.4 done** (issue #72, PR #73, merge commit `5bb169e`, 8 of 8 checks green): `LoginAttemptRepo` frozen, `PostgresLoginAttemptRepo` over a `login_attempts` table, and a purge script. Nothing writes to the table until M2.7. See the M2.4 ticket card
- **M2.5 done** (issue #74, PR #75, merge commit `7bce020`, 11 commits, 8 of 8 checks green): `RegistrationService`, `RegisterInput` and `RegisteredUser` in `credentials/users/`, the shared input rules (`normalize_password()`, password and email limits, a registration-only email shape check) and `ErrorCode.INVALID_EMAIL`. Service only; nothing calls it yet. See the M2.5 ticket card
- **M2.6 done** (issue #76, PR #77, merge commit `b0c1f9c`, 6 commits, 8 of 8 checks green): `PasswordAuthenticator` in `credentials/login/`: one indistinguishable failure, a dummy-hash verify on the unknown-user path, rehash on login. Service only; nothing calls it yet. See the M2.6 ticket card
- **M2.7 done** (issue #78, PR #79, merge commit `92a6982`, 12 commits, 8 of 8 checks green): `ThrottledAuthenticator` in `credentials/login/`, `AppError.throttled` and two `AuthSettings` fields. Service only; nothing calls it yet. See the M2.7 ticket card
- **M2.8 done** (issue #80, PR #81, merge commit `fe4928e`, 7 commits, 8 of 8 checks green): integration tests on real PostgreSQL for register, login, rehash, indistinguishable failures, throttling and secret safety, in `trutina-storage-postgres`. Service level only; nothing calls the services yet. M2 is complete. See the M2.8 ticket card
- Register is a service-level use case only, with no HTTP route **(done in M2.5)**
- Verify the hashing library on Python 3.14; set cost parameters; rehash on login; run hashing off the event loop with a bounded concurrency limit **(library, parameters and offloading done in M2.2; rehash on login done in M2.6)**
- Unknown email and wrong password give identical status, code and message, no interpolated context, and a dummy hash on the unknown-user path (assert via a fake that the dummy verify runs; no wall-clock timing tests). A disabled account gets the same invalid-credentials response at login **(done in M2.6; end to end in M2.8)**
- Login rate limiting in a dedicated table, keyed on IP and email together, throttling rather than locking the account; client IP is read from `X-Forwarded-For` only from configured trusted proxies; expired rows are deleted opportunistically, plus a documented purge script (no scheduler exists) **(done in M2.7 at service level; the trusted-proxy client IP is M3.6)**
- `AuthEventSink` protocol with a no-op default **(first used by `auth.login_throttled` in M2.7)**
- Credential fields are `SecretStr` and are excluded from `FieldViolation.value` and from 422 `details` (including FastAPI request-validation input), with a test that a rejected password never appears in a response or log
- `RefreshTokenHasher` is a separate port using plain SHA-256, never `PasswordHasher` (P4); the contract exists from M0b
- Finalize the provisional `LoginAttemptRepo` contract with the throttling logic, and add the first `AUTH_*` error codes (API and CLI catalog entries and the parity test in the same PR; landed in M2.3) **(LoginAttemptRepo contract frozen and adapter added in M2.4; the throttling logic landed in M2.7, D31)**

## Milestone summary

**M2**
Outcome: Services can register a user and verify credentials safely; no HTTP route or token exists. Status: M2.0 done (PR #65), M2.1 done (PR #67), M2.2 done (issue #70), M2.3 done (PR #69), M2.4 done (issue #72, PR #73), M2.5 done (issue #74, PR #75), M2.6 done (issue #76, PR #77), M2.7 done (issue #78, PR #79); M2.8 done (issue #80, PR #81). M2 is complete. Gate: dev and test only; nothing here is exposed by a route.

## Cards

### WP M2-A: Shared safeguards (parallel lane, no mutual dependencies)

### M2.0 — Redaction set extension

**Needs:** none

#### Spec

- **Scope:** Purpose: no credential reaches a log sink once M2 logs request-shaped data. Ticket premise was partly wrong: the substring markers (`password`, `token`, `authorization`, matched on the lower-cased key) already covered `refresh_token`, `access_token`, `password_hash` and `Authorization`, so no marker was added. The real gap was that `_redact_value` did not recurse: a secret one level below an innocent key (`{"headers": {"Authorization": ...}}`) or inside a list of dicts was logged in clear. `_redact_value` now recurses into dicts (each value under its own key) and lists and tuples (under the parent key), and masks a credential-shaped key whatever its value type. The input is not mutated (D23).
- **Excludes:** No auth code, no new marker, no free-text or exception-text scrubbing, no value-pattern detection, no change to monetary-key dropping.
- **Needs:** none
- **Accept:**
  - [ ] Met: no secret value appears in rendered output for 7 credential keys at the top level, inside `context`, nested in dicts, and inside a list of dicts.
  - [ ] Met: credential redaction holds at every level and in both JSON and console formats.
  - [ ] Met: nested URI credentials are masked; non-secret context and monetary behavior are unchanged.
  - [ ] Met: the negative check confirmed 10 of the new tests fail on the old code.

#### Outcome

Issue #64 closed. PR #65 merged to `main` as merge commit `0ab8974` (3 commits: `147ac9a`, `4999111`, `34e3162`; branch `feat/64-redact-credential-log-keys`, 8 of 8 checks green). Files: `processors.py`, `tests/test_redaction_contract.py`, observability `CONTEXT.md`.

Evidence: G0, lane observability. Closed end to end by M2.8 (R4)

---

### M2.1 — Secret-safe validation errors

**Needs:** none

#### Spec

- **Scope:** Purpose: a rejected credential never reaches a violation record, a response or a log once M2 adds credential fields. The leak was in `get_field_violations()`, which stringified Pydantic's rejected input into `FieldViolation.value`, including the whole parent object that a `missing` error carries: a payload with `password` and no `email` produced an error on `email` whose value held the password. New `trutina.shared.secret` (`SECRET_FIELD_MARKERS`, `safe_input_text`): the input is masked when any segment of the error location is credential-shaped, and credential-keyed entries are masked recursively inside container inputs. The input is not mutated, and domain codes (carried in `value` as a code string, not as input) are preserved (D24). Ticket premise partly wrong: the API 422 body and CLI panels never read `value`, so those layers needed regression proof, not code. Proven with a test-only `SecretProbe` model and `make_secret_probe_payload()` in `tests/factories/secret.py`, over the API's three validation paths (request, mapper, service) and both CLI error-boundary validation branches.
- **Excludes:** No real credential schema, no login or register route, no value-pattern detection, no change to the observability processors.
- **Needs:** none
- **Accept:**
  - [ ] Met: a rejected credential, including one supplied beside a failing or missing field, appears in no `FieldViolation` value or repr.
  - [ ] Met: the 422 body (including `details`) contains no secret on the request, mapper and service paths, and no captured log record contains it.
  - [ ] Met: both CLI error-boundary validation branches render and log no secret.
  - [ ] Met: non-secret violations are unchanged (`field`, `code`, `value`), and a domain code on a credential field is still preserved.
  - [ ] Met: CI green (QG1 to QG7).

#### Outcome

Issue #66 closed. PR #67 merged to `main` as merge commit `a348d50` (9 commits, branch `feat/66-secret-safe-validation-errors` deleted, 8 of 8 checks green). M2.5 and M3.7 build on it.

Evidence: G0, lanes shared, api, cli. Re-verified on real routes in M3.7

---

### M2.3 — Auth error codes and catalogs

**Needs:** none

#### Spec

- **Scope:** Purpose: M2.6 and M2.7 can raise errors both apps already render. `AUTH_INVALID_CREDENTIALS` (`auth.invalid_credentials`, 401) and `AUTH_THROTTLED` (`auth.throttled`, 429), in a new Auth group of the shared `ErrorCode`, with API catalog entries, CLI `ERRORS` and `HINTS` entries, one CLI `FIELD_LABELS` entry (`credentials`, for invalid credentials only) and the parity tests, all in one PR (D25). The API's `_response_headers` now receives the error's context and emits `Retry-After` for `AUTH_THROTTLED` only when `context["retry_after_seconds"]` is a non-negative integer string (ASCII digits, leading zeros normalized); a missing or malformed value keeps the 429 and omits the header. Intermediate state (R3): nothing raises either code until M2.6 and M2.7.
- **Excludes:** Token codes and `AUTH_USER_DISABLED` (M3), any 403 (M5), `WWW-Authenticate` (M3.6), raise sites, an `AppError` constructor for the throttle delay, throttle policy.
- **Needs:** none
- **Accept:**
  - [ ] Met: both codes exist with the decided values and no existing value changed (pinned by `test_codes.py`).
  - [ ] Met: parity tests pass in both apps; with the API catalog entries missing, 8 tests failed (observed before the entries were added).
  - [ ] Met: the invalid-credentials entries have no placeholders, and an API response for it contains no context value.
  - [ ] Met: a valid `retry_after_seconds` gives 429 with `Retry-After`; missing, negative, decimal, CRLF-injection and non-ASCII-digit values give 429 with no header and no exception.
  - [ ] Met: each code logs one INFO failure line in the API handler and in `error_boundary()`; neither is in the CLI `_ERROR_LEVEL_CODES`.
  - [ ] Met: CI green (QG1 to QG7).

#### Outcome

Issue #68 closed. PR #69 merged to `main` as merge commit `919c131` (7 commits, branch `feat/68-auth-error-codes` deleted, 8 of 8 checks green). Premise checks: `_response_headers` took only the code, so it gained a context argument; the CLI formatter lets a `field` context key override `FIELD_LABELS`, recorded as a constraint on M2.6. Unblocks M2.6 and the M2.7 raise site; the end-to-end criteria close in M2.8 and M3.7 (R4).

Evidence: G0, lanes shared, api, cli. 844 unit tests passed locally in these lanes before merge

---

### WP M2-B: Credential building blocks

### M2.2 — Password hasher

**Needs:** M0b (done)

#### Spec

- **Scope:** Purpose: M2.5 and M2.6 have a real hasher to consume. `Argon2PasswordHasher` in `credentials/argon2_hasher.py`, exported from the package root: Argon2id through `argon2-cffi` 25.1.0 (verified on Python 3.14.4 on Windows and in the Docker builder). The constructor takes plain keyword-only `time_cost`, `memory_cost_kib`, `parallelism` and `max_concurrency`; the package does not import `trutina-config`. Blocking work runs through `asyncio.to_thread` behind a semaphore. `verify` returns `False` for any malformed hash; `needs_rehash` returns `True` for a hash made with other parameters and for a malformed one (the contract was silent on the latter). `AuthSettings` gained `password_time_cost` (3), `password_memory_cost_kib` (65536), `password_parallelism` (1) and `password_hash_concurrency` (4), validated only for Argon2 shape (D8, D26). One hash at the defaults took about 260 ms on a development machine (a single run); peak hashing memory is about 256 MiB per process. Dependencies: `argon2-cffi` 25.1.0 and `argon2-cffi-bindings` 26.1.0. `.env.test.example` was corrected to the `TRUTINA_TEST_` prefix in the same PR, because the new test-namespace entries needed it.
- **Excludes:** No use case, storage, wiring into an app, dummy hash, password length cap, Unicode normalization or weak-parameter rejection.
- **Needs:** M0b (done)
- **Accept:**
  - [ ] Met: round trip (ASCII and non-ASCII), salting, parameters embedded in the hash, malformed hashes verify `False`, rehash behavior, off-thread execution, the concurrency bound and no logs, in the authentication unit lane.
  - [ ] Met: `AuthSettings` fields, defaults and bounds, including memory per lane; `Settings()` and `TestSettings()` still build with no keys.
  - [ ] Met: `lint-imports` keeps 7 contracts; Docker smoke passes (five migrations from empty, API healthy, structured logging confirmed); CI green.

#### Outcome

Issue #70 closed. Branch `feat/70-password-hasher` (12 commits) merged to `main` with CI green; the PR number and merge commit are not recorded here yet. Unblocks M2.5 and M2.6; the end-to-end security criteria close in M2.8 (R4).

Evidence: G0, G-DOCKER, lanes authentication, config

---

### M2.4 — Login-attempt storage

**Needs:** M1b.1; ran in parallel with M2.2

#### Spec

- **Scope:** Purpose: M2.7 has a frozen contract and a real store to throttle against. `LoginAttemptRepo` is frozen: attempts match on IP as given and on the email in its `normalize_email()` form, times are aware UTC from `Clock`, no method raises a domain error, and "provisional" is removed from the docstring and docs. `PostgresLoginAttemptRepo` and `LoginAttemptModel` live in `storage_postgres/login_attempt/`, over a `login_attempts` table (D27), migration `4794a1756a02` on top of `41065b2e2190` with a tested downgrade. `login_attempts` is in the `clean_pg_db` truncate list and `postgres_login_attempt_repo` is a fixture. `FakeLoginAttemptRepo` now matches emails through `normalize_email()`. `tools/purge-login-attempts.py` (`--older-than-hours`, default 24) is the documented purge path; run once against a development database with two seeded rows, it removed the old row and kept the recent one. Nothing writes to the table until M2.7.
- **Excludes:** No throttle policy, no client-IP extraction (M3.6), no input length cap (M2.6), no scheduler.
- **Needs:** M1b.1; ran in parallel with M2.2
- **Accept:**
  - [ ] Met: count within a window (inclusive of `since`), IP and email isolation, case and whitespace-insensitive email matching, scoped `clear`, and strict `purge_before` with its deleted count, on real PostgreSQL and in the fake.
  - [ ] Met: normalized email, given IP and an aware timestamp stored as specified; attempts for an email with no user are recorded (no foreign key).
  - [ ] Met: an integration test shows the repository logs neither the IP nor the email.
  - [ ] Met: migration round trip restores head in a `finally` block, and `alembic check` reports no new operations.
  - [ ] Met: `lint-imports` keeps 7 contracts; Docker smoke applies all six migrations from an empty database; CI green (QG1 to QG7).

#### Outcome

Issue #72 closed. PR #73 merged to `main` as merge commit `5bb169e` (14 commits, branch `feat/72-login-attempt-storage` deleted, 8 of 8 checks green). Verified locally before the last commits: `tools/pre-push.sh` green (1486 unit tests), 62 unit tests in the authentication lane, 180 unit and 93 integration tests in infra postgres. Unblocks M2.7; the end-to-end criteria close in M2.8 (R4).

Evidence: G0, G-DOCKER, lanes authentication, infra postgres, `alembic check`

---

### WP M2-C: Use cases

### M2.5 — Register use case (service only)

**Needs:** M2.1, M2.2

#### Spec

- **Scope:** Purpose: a user can be created with a normalized email and an Argon2id-hashed password through one service, with every input rule that login must reuse decided once. `RegistrationService.register` in `credentials/users/registration.py`, with `RegisterInput` and `RegisteredUser`, all exported from the package root. Order: validate, normalize, duplicate pre-check, hash, create an active user (UUID from the service, `created_at` from `Clock`), emit one `auth.user_registered` event carrying `subject_id` only. Input rules (D28): `normalize_password()` (NFKC, then strip), `MAX_PASSWORD_LENGTH` 128, a registration-only minimum of 8, `MAX_EMAIL_LENGTH` 254 and a minimal email shape check. Service shape (D29): rules checked in the service, not in Pydantic validators; `DUPLICATE_USER_EMAIL` propagates; a failure to build the `User` is `UNKNOWN_ERROR`. New `ErrorCode.INVALID_EMAIL` with API and CLI catalog entries and parity tests. `trutina-authentication` now depends on `trutina-shared`. The credential modules were grouped into `passwords/`, `users/` and `login/` with no behavior change. Intermediate state (R3): nothing wires the service into an app.
- **Excludes:** No HTTP route or CLI command, no login, throttling or tokens, no email verification, password strength or breached-password check, no change to the `User` model or the `UserRepo` contract, no `AuthSettings` field.
- **Needs:** M2.1, M2.2
- **Accept:**
  - [ ] Met: registering `" Ann@Example.com "` creates one active user stored as `ann@example.com` whose hash is the hasher's output, with one hash call.
  - [ ] Met: a second registration in another casing raises `DUPLICATE_USER_EMAIL` before hashing, with no address in its context; a duplicate reported by `create` in a race passes through unchanged.
  - [ ] Met: an over-maximum, under-minimum, blank or malformed-email input raises `ValidationAppError` on the right field with no hasher call and no create; email and password violations are reported together and the password value is masked.
  - [ ] Met: success emits one event with the subject id only and rejections emit none; nothing returned or raised carries the password or its hash.
  - [ ] Met: `lint-imports` keeps 7 contracts. The manual negative check is not recorded here.

#### Outcome

Issue #74. PR #75 merged to `main` as merge commit `7bce020` (11 commits, branch `feat/74-register-use-case` deleted, 8 of 8 checks green). Premise checks: the ticket's "must not trim" wording was revised, so passwords are trimmed at the edges after NFKC (D28); no existing `ErrorCode` fit a malformed email, so `INVALID_EMAIL` was added; a Pydantic validator would have downgraded it to `UNKNOWN_ERROR`, so the checks live in the service. Verified locally before merge: 931 unit tests across the shared, api, cli and authentication lanes; ruff, `ty` and 7 import contracts clean; Docker smoke applied all six migrations (run when the dependency changed). Unblocks M2.6; the end-to-end criteria close in M2.8 (R4).

Evidence: G0, G-DOCKER, lanes authentication, shared, api, cli

---

### M2.6 — Login verification

**Needs:** M2.2, M2.3, M2.5 (done)

#### Spec

- **Scope:** Purpose: M2.7 and the M3 session service have a login check to build on. `PasswordAuthenticator` in `credentials/login/password_authenticator.py`, implementing `Authenticator` and exported from the credentials folder and the package root. Collaborators are a user repo, a hasher and a dummy hash, all keyword-only; an async `create()` makes the dummy hash once with `hash()` of a random value, so it uses the current parameters. Order: cap the raw password, normalize it with `normalize_password()`, normalize and cap the email, look up, verify against the user's hash or the dummy hash, check `is_active`, rehash a stale hash, return `Identity` (D30). Unknown email, wrong password, disabled account, blank password and over-limit input raise one `AUTH_INVALID_CREDENTIALS` with an empty context. Over-limit and blank input is rejected before any lookup or hash. The registration-only minimum length and email shape check are not applied. `client_ip` is accepted and unused. Intermediate state (R3): nothing wires it into an app, so `AUTH_INVALID_CREDENTIALS` now has a raiser but no route to carry it.
- **Excludes:** No throttling, `Clock`, events, tokens, routes or commands, no `AuthSettings` field, no change to the `UserRepo`, `PasswordHasher` or `Authenticator` signatures.
- **Needs:** M2.2, M2.3, M2.5 (done)
- **Accept:**
  - [ ] Met: a fake records the dummy verify (`verify_calls == [dummy_hash]`), with no timing assertion.
  - [ ] Met: the unknown-email, wrong-password, disabled and over-limit failures are indistinguishable in code, context and repr.
  - [ ] Met: a stale hash is rehashed with the normalized password after a successful login, and never after a failed or disabled one; a rehash storage error propagates unchanged.
  - [ ] Met: blank and over-limit input never reaches the repo or the hasher, and input at the limits is accepted.
  - [ ] Met: the registration minimum and the email shape check are not applied, and no error carries the password.
  - [ ] Met: `lint-imports` keeps 7 contracts.
  - [ ] Not recorded here: the manual negative checks (dummy verify removed; a `field` key added to the context).

#### Outcome

Issue #76 closed. PR #77 merged to `main` as merge commit `b0c1f9c` (6 commits, branch `feat/76-login-verification` deleted, 8 of 8 checks green). Verified locally: ruff, `ty` and 7 import contracts clean; 153 unit tests in the authentication lane; `tools/pre-push.sh` green with lane coverage OK (1752 collected). No migration or dependency change, so no Docker smoke run was needed. Premise checks: the ticket's "times from `Clock`" needed no clock because nothing in M2.6 uses time; `hash()` is async, so the dummy hash comes from `create()`. Unblocks M2.7; the end-to-end criteria close in M2.8 (R4).

Evidence: G0, lane authentication

---

### M2.7 — Throttling

**Needs:** M2.4, M2.6 (done)

#### Spec

- **Scope:** Purpose: repeated failed logins are slowed without locking anyone out, and without costing a hash. `ThrottledAuthenticator` in `credentials/login/throttled_authenticator.py`, a decorator over any `Authenticator`, exported from the package root; `PasswordAuthenticator` and the `Authenticator` contract change in docstrings only. Failures are counted per client IP and `normalize_email()` of the attempted address within a sliding window, before the inner call and without looking at the account. At `login_max_failures` (5) within `login_window_seconds` (900) it raises `AUTH_THROTTLED` with `retry_after_seconds` equal to the window. It counts every `AUTH_INVALID_CREDENTIALS` from the inner authenticator, and never a throttled attempt, another error or an email over `MAX_EMAIL_LENGTH`. A missing IP is stored as `"unknown"`. A success clears the pair only if failures existed; each recorded failure purges rows older than the window; attempt-store errors propagate unchanged. One event, `auth.login_throttled`, carries the delay only. New `AppError.throttled` in `trutina-shared` owns the context key (D32), and `AuthSettings` gained the two limits (D31). Intermediate state (R3): nothing wires it into an app, so `AUTH_THROTTLED` now has a raiser but no route to carry it.
- **Excludes:** No `X-Forwarded-For` parsing (M3.6), no per-IP or per-email global limit, no change to the `LoginAttemptRepo` contract or the migration history, no CLI label for the throttled code, no wiring into an app.
- **Needs:** M2.4, M2.6 (done)
- **Accept:**
  - [ ] Met: N failures within the window throttle further attempts for that IP and email, including for an unknown email, with the same error as a known one and no hashing while throttled.
  - [ ] Met: a success clears the counter, and only that pair's (pinned by a test in the last commit); rows older than the window are purged when a failure is recorded.
  - [ ] Met: the account is never locked: after the window, and for another IP or email, login proceeds.
  - [ ] Met: a throttled attempt is not recorded; an over-limit email touches no storage; other errors are not recorded.
  - [ ] Met: the event carries no email, IP or password; no log line is emitted.
  - [ ] Met: `lint-imports` keeps 7 contracts; CI green (8 of 8).
  - [ ] Not recorded here: the manual negative checks (threshold off by one; count moved after the inner call).

#### Outcome

Issue #78 closed. PR #79 merged to `main` as merge commit `92a6982` (12 commits, branch `feat/78-login-throttling` deleted, 8 of 8 checks green). Verified locally before merge: ruff, `ty` and 7 import contracts clean; unit lanes shared 113, config 83 and authentication 178 (counts taken before the last commit, which added one test); `tools/pre-push.sh` green; a documentation sweep removed every statement that throttling was still to come. No migration or dependency change, so no `alembic check` and no local Docker smoke (CI's QG7 passed). Premise checks: the frozen `LoginAttemptRepo` has no oldest-failure query, so the retry delay is the window length; the 11th and 12th commits (docs sweep and the clear-only-its-own-pair test) were added after review. Unblocks M2.8; the end-to-end criteria close there and in M3.7 (R4).

Evidence: G0, lanes authentication, shared, config

---

### WP M2-D: Closeout

### M2.8 — Integration and security verification

**Needs:** M2.0 to M2.7 (done)

#### Spec

- **Scope:** Purpose: M2.0 to M2.7 were each proven against fakes; this proves them together on real PostgreSQL. One test file, `storage_postgres/shared/tests/test_credentials_integration.py`, runs the real `RegistrationService`, `PasswordAuthenticator` and `ThrottledAuthenticator` over `PostgresUserRepo` and `PostgresLoginAttemptRepo` with a real Argon2id hasher (cheapest parameters, wrapped to record calls), a `FakeClock` and a fake event sink (D33). Groups: register then login (differently typed email, argon2id hash stored with no plaintext, duplicate rejected before hashing, one secret-free event, rehash on login and none after a failed login); indistinguishable failures (unknown, wrong, disabled and over-limit input; the dummy-hash verify; reactivation restores login); throttling (limit reached, the correct password refused while throttled with no hashing, throttled attempts not recorded, known and unknown emails identical, the window boundary, never locking, clearing only the successful pair, purge on record, normalized email and the unknown IP); and a leak check over logs, error contexts, events and the `login_attempts` and `audit_events` tables, with a positive control for the log collector. The last commit of the PR extended the registration tests; which cases it added and the final test count are not recorded here. Docs: authentication, storage-postgres, config, ARCHITECTURE, AGENTS, PROJECT_CONTEXT, ROADMAP, README and `.env.test.example` corrected for drift from M2.5 to M2.7.
- **Excludes:** No new behavior, route, command or migration. No route-level proof. No production file changed.
- **Needs:** M2.0 to M2.7 (done)
- **Accept:**
  - [ ] Met: no plaintext password and no stored hash appears in captured logs, error contexts, events or the `login_attempts` and `audit_events` tables across a scenario that includes a rehash and a throttle; the users table holds only the Argon2 hash. The check does not assert the absence of emails or IPs, which `login_attempts` stores by design (D27).
  - [ ] Met: throttling works against real PostgreSQL, including the inclusive window boundary and the strict purge.
  - [ ] Met at service level: unknown email, wrong password, disabled account and over-limit input are indistinguishable, and the unknown-email path verifies against the dummy hash.
  - [ ] Met: no migration, dependency or startup change, so G-DOCKER did not apply; CI's Docker smoke job (QG7) passed.
  - [ ] Not closed here, by design: the 422 body on a real route, `Retry-After` end to end, and the real structlog redaction pipeline with a real credential flow. These stay with M3.7 and M3.8 (R4).
  - [ ] Not recorded here: the manual negative checks (dummy verify removed; threshold off by one; the record moved before the inner call; a `field` key added to the context).

#### Outcome

Issue #80 closed. PR #81 merged to `main` as merge commit `fe4928e` (7 commits, branch `test/80-credentials-integration-verification` deleted, 8 of 8 checks green). Verified locally before merge: `tools/pre-push.sh`, ruff, `ty` and 7 import contracts clean, lane coverage OK, authentication unit lane 179 passed, infra postgres integration lane 116 passed. The first run of the suite failed one test because it assumed a stale hash survives a login under a different hasher; the code was correct, and the test was fixed. The failure showed that two processes with different hash parameters rewrite each other's hash (known gap). Premise check: criteria needing the real structlog pipeline or a real route cannot close at this layer. M2 is complete; unblocks M3.4 and M4.5.1 on the credentials side.

Evidence: G0, lane integration infra postgres, CI QG1 to QG7
