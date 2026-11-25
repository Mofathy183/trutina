# Gaps

## Index

| ID | Kind | Milestone | Lead |
|---|---|---|---|
| GAP-M0-01 | Known gap | M0 | the lane list in `check-lane-coverage.sh` duplicates the selectors in the workflow files… |
| GAP-M0-02 | Known gap | M0 | `tools/docker-smoke.sh` needs `MSYS_NO_PATHCONV=1` on Windows Git Bash, and fails if another process… |
| GAP-M1-01 | Known gap | M1 | PR #53 and PR #54 were both merged with a merge commit,… |
| GAP-M1-02 | Known gap | M1 | `created_by` is null on rows written before migration `a3f1c9d2b7e4`. Null means pre-attribution;… |
| GAP-M1-03 | Known gap | M1 | `audit_events` is append-only by repository convention only (D22). A role with UPDATE… |
| GAP-M1-04 | Known gap | M1 | account changes made before migration `41065b2e2190` have no audit row and cannot… |
| GAP-M1-05 | Known gap | M1 | `ty` cannot see calls made through untyped fixtures, so a changed repository… |
| GAP-M1-06 | Known gap | M1 | a unit test can pass by quietly reaching a developer's local PostgreSQL.… |
| GAP-M1-07 | Known gap | M1 | a model change without its migration failed 23 integration tests with a… |
| GAP-M1-08 | Known gap (M1b) | M1 | email format is checked only at registration, by a minimal shape rule… |
| GAP-M1-09 | Known gap | M1 | `REQUEST_VALIDATION_ERROR` has no catalog entry in either app. It is used only… |
| GAP-M2-01 | Known gap | M2 | log redaction is key-based only. A secret inside exception text, or interpolated… |
| GAP-M2-02 | Known gap | M2 | the redaction markers match by substring, so hyphenated or cookie-style names (`x-api-key`,… |
| GAP-M2-03 | Known gap | M2 | `_redact_value` and `coerce_context` have no cycle protection; a cyclic `context` would raise… |
| GAP-M2-04 | Known gap | M2 | monetary-key dropping does not recurse and applies only at the top level… |
| GAP-M2-05 | Known gap | M2 | credential detection in validation errors is name-based (D24): a credential field whose… |
| GAP-M2-06 | Known gap | M2 | the API 422 body returns Pydantic's `msg`. A credential validator that interpolates… |
| GAP-M2-07 | Known gap | M2 | `redact_input()` has no cycle protection and does not look inside sets, and… |
| GAP-M2-08 | Known gap | M2 | the CLI titles every `AppError` panel "Validation Error", including not-found, conflict and… |
| GAP-M2-09 | Constraint on M2.6, met (D30) | M2 | the CLI formatter lets a `field` key in `AppError.context` override `FIELD_LABELS`, so… |
| GAP-M2-10 | Known gap | M2 | `AUTH_THROTTLED` has no CLI field label, so its panel shows the field… |
| GAP-M2-11 | Known gap | M2 | `Retry-After` is verified at handler level only, and the key `retry_after_seconds` is… |
| GAP-M2-12 | Known gap | M2 | the hasher itself still has no length limit. `RegistrationService` and `PasswordAuthenticator` enforce… |
| GAP-M2-13 | Known gap | M2 | a cancelled caller releases its hash slot while the worker thread finishes,… |
| GAP-M2-14 | Known gap | M2 | the hasher does not reject weak parameters, and `AuthSettings` validates shape only… |
| GAP-M2-15 | Decided in M2.5 (D28) | M2 | passwords are normalized with NFKC and then stripped at the edges by… |
| GAP-M2-16 | Constraint on M2.6, met (D30) | M2 | the dummy hash for the unknown-user path must be made once at… |
| GAP-M2-17 | Known gap | M2 | the default hashing parameters rest on one 260 ms single-run measurement and… |
| GAP-M2-18 | Known gap | M2 | the attempted email passed to `LoginAttemptRepo` is not length-capped, so junk or… |
| GAP-M2-19 | Known gap | M2 | `login_attempts` holds attempted addresses in plain normalized form, including addresses that belong… |
| GAP-M2-20 | Known gap | M2 | a naive datetime passed to `LoginAttemptRepo` is the caller's bug and is… |
| GAP-M2-21 | Known gap | M2 | `tools/purge-login-attempts.py` has no automated test and sits outside `ty` and the lane-coverage… |
| GAP-M2-22 | Known gap | M2 | the API Docker runtime image copies `packages/` and `apps/api/` only, so `tools/purge-login-attempts.py`… |
| GAP-M2-23 | Decided at the service in M2.5 (D29), open for routes | M2 | `RegistrationService` passes `DUPLICATE_USER_EMAIL` to its caller, which reveals which emails are registered,… |
| GAP-M2-24 | Known gap | M2 | nothing wires `RegistrationService`, `PasswordAuthenticator`, `ThrottledAuthenticator` or `SessionService` into an app, and no… |
| GAP-M2-25 | Known gap | M2 | `PasswordAuthenticator` rejects blank and over-limit input faster than a wrong password, because… |
| GAP-M2-26 | Known gap | M2 | a rehash write failure fails the login (D30). The rehash is also… |
| GAP-M2-27 | Known gap | M2 | the dummy hash is made once per process, so a later change… |
| GAP-M2-28 | Known gap | M2 | even with throttling (M2.7), every attempt below the limit holds one of… |
| GAP-M2-29 | Known gap | M2 | the manual negative checks for M2.6 (dummy verify removed; a `field` key… |
| GAP-M2-30 | Known gap | M2 | passwords are checked for length only (no complexity rule, no breached-password check),… |
| GAP-M2-31 | Known gap | M2 | the registration duplicate pre-check and the insert are not atomic. The `uq_users_email`… |
| GAP-M2-32 | Constraint on M2.6, met (D30) | M2 | the minimum password length and the email shape check are registration-only and… |
| GAP-M2-33 | Constraint from M2.4, met (D31) | M2 | the attempted email is recorded only if it passed `MAX_EMAIL_LENGTH`; `ThrottledAuthenticator` skips… |
| GAP-M2-34 | Decided in M2.7 (D32) | M2 | `AppError.throttled` owns the `retry_after_seconds` key. The API handler still reads it through… |
| GAP-M2-35 | Known gap | M2 | the throttle's check and its later record are not atomic, so concurrent… |
| GAP-M2-36 | Known gap | M2 | throttling is per IP and email only (locked decision 7). One IP… |
| GAP-M2-37 | Known gap | M2 | `retry_after_seconds` is the window length, an upper bound, so a client may… |
| GAP-M2-38 | Known gap | M2 | one `auth.login_throttled` event is emitted per rejected attempt, which is noisy under… |
| GAP-M2-39 | Known gap | M2 | purge runs only when a failure is recorded, so rows linger if… |
| GAP-M2-40 | Known gap | M2 | the manual negative checks for M2.7 (threshold off by one; the count… |
| GAP-M2-41 | Known gap | M2 | the client IP reaching `ThrottledAuthenticator` is whatever the caller passes. Until trusted-proxy… |
| GAP-M2-42 | Known gap | M2 | two processes configured with different hash parameters rewrite each other's stored hash,… |
| GAP-M2-43 | Known gap | M2 | the M2.8 log check uses a stdlib handler because storage tests cannot… |
| GAP-M2-44 | Known gap | M2 | the manual negative checks for M2.8 (dummy verify removed; threshold off by… |
| GAP-M3-01 | Known gap (ADR 0001) | M3 | there is no automatic detection of a stolen session token. It works… |
| GAP-M3-02 | Known gap (ADR 0001) | M3 | every authenticated request, reads included, now needs a database connection, and the… |
| GAP-M3-03 | Closed in M3.1 (PR #87) | M3 | the removal of `signing_keys` and `active_kid` from `AuthSettings`, the token fakes and… |
| GAP-M3-04 | Known gap (ADR 0001) | M3 | `last_used_at` is touched at most every 5 minutes, so idle expiry is… |
| GAP-M3-05 | Known gap (ADR 0001) | M3 | a session token travels only in the `Authorization` header, so the hyphenated… |
| GAP-M3-06 | Known gap (ADR 0002) | M3 | a thief holding an `api` token can read data and create draft… |
| GAP-M3-07 | Known gap (ADR 0002) | M3 | a wrong password on `/auth/reauth` is a 401 that does not end… |
| GAP-M3-08 | Known gap (ADR 0002) | M3 | revoking a user's other sessions on a password change has no route… |
| GAP-M3-09 | Known gap (ADR 0002) | M3 | no cap on sessions per user, and the session purge script (`tools/purge-sessions.py`,… |
| GAP-M3-10 | Closed in M3.3 (PR #89) | M3 | the wording gap around `touch`. ADR 0002 section 4 was amended to… |
| GAP-M3-11 | Known gap (M3.1) | M3 | `PostgresSettings.pool_timeout_s` is declared and not passed to the engine, and how a… |
| GAP-M3-12 | Known gap (M3.1) | M3 | the session lifetime settings have no upper bound and an idle value… |
| GAP-M3-13 | Known gap (M3.1) | M3 | a duplicate session token hash was undefined in `SessionRepo`; since M3.3 the… |
| GAP-M3-14 | Known gap (M3.1) | M3 | a leftover `TRUTINA_AUTH__SIGNING_KEYS__*` or `TRUTINA_AUTH__ACTIVE_KID` value is ignored silently, with no warning… |
| GAP-M3-15 | Known gap (M3.1) | M3 | `FakeSessionRepo` stands in for the join to `users` with a `FakeUserRepo`. The… |
| GAP-M3-16 | Closed in M3.4 (PR #91) | M3 | the missing automatic purge of `sessions`. `SessionService` deletes sessions dead longer than… |
| GAP-M3-17 | Known gap (M3.3) | M3 | `tools/purge-sessions.py` has no automated test and sits outside `ty` and the lane-coverage… |
| GAP-M3-18 | Known gap (M3.3) | M3 | `touch` and `mark_reauthenticated` do not re-check expiry (the contract no-ops only an… |
| GAP-M3-19 | Known gap (M3.3) | M3 | the expiry columns of `sessions` are not indexed, so `purge_before` scans the… |
| GAP-M3-20 | Known gap (M3.3) | M3 | a rejected `create` reports only the violated constraint name, with no driver… |
| GAP-M3-21 | Known gap (M3.3) | M3 | tests for a bad `client_kind` rejected by PostgreSQL, a reactivated user's session… |
| GAP-M3-22 | Known gap (M3.3) | M3 | the manual negative checks, the `git grep` audit of every `SessionRepo` implementer… |
| GAP-M3-23 | Known gap (M3.4) | M3 | `SessionService` purges on every login with one unbounded `DELETE` (D38). `sessions` has… |
| GAP-M3-24 | Known gap (M3.4) | M3 | re-authentication goes through `ThrottledAuthenticator`, so a failed re-authentication counts toward the same… |
| GAP-M3-25 | Known gap (M3.4) | M3 | the revoke-all event is `auth.session_revoked` with `client_kind` set to `"all"`. ADR 0002… |
| GAP-M3-26 | Known gap (M3.4) | M3 | the `cli` kind being exempt from step-up is a caller convention. `require_recent_auth`… |
| GAP-M3-27 | Known gap (M3.4) | M3 | edge behaviors of the service. Logout of an expired but unrevoked token… |
| GAP-M3-28 | Known gap (M3.4) | M3 | `sessions/service.py` imports `credentials` (`Authenticator`, `UserRepo`) by submodule path. `credentials` never imports `sessions`.… |
| GAP-M3-29 | Known gap (M3.4) | M3 | tests not written for `repr` and `str` of the validation result, for… |
| GAP-M3-30 | Known gap (M3.4) | M3 | the existing handler and boundary tests that parametrize over auth codes (`test_handlers.py`,… |
| GAP-M3-31 | Known gap (M3.4) | M3 | verification not recorded here: per-test output of the manual negative checks (the… |
| GAP-M4-01 | At M4c | M4 | write down expected load, measure a baseline, revise the provisional thresholds once,… |
| GAP-M4-5-01 | At M4.5 | M4-5 | the CLI session path, whose table, `cli` kind and lifetimes are decided… |
| GAP-M5-01 | At M5 | M5 | the permission matrix, whether read routes load the access state per request… |
| GAP-UNASSIGNED-01 | Deferred | UNASSIGNED | password reset and the email provider, OAuth, MFA, email verification, API keys,… |
| GAP-UNASSIGNED-02 | Known gap until reset ships | UNASSIGNED | a locked-out user has no self-service recovery. Record it in the authentication… |
| GAP-UNASSIGNED-03 | Known gap | UNASSIGNED | the empty revision `7e1b970f05a7` ("check") remains in the migration history. It is… |
| GAP-UNASSIGNED-04 | Known gap | UNASSIGNED | PR #75's commits mix the scopes `auth` and `authentication`, and no list… |
| GAP-UNASSIGNED-05 | Open (ADR 0002) | UNASSIGNED | whether account update, which can change the category and so the normal-balance… |
| GAP-UNASSIGNED-06 | Deferred (ADR 0002) | UNASSIGNED | cookie transport, the Origin check, CORS, CSP and cookie redaction markers wait… |
| GAP-UNASSIGNED-07 | Known gap | UNASSIGNED | the merge commit for PR #83 (ADR 0001, M3.0) is not recorded… |
| GAP-UNASSIGNED-08 | Deferred to the OAuth milestone | UNASSIGNED | drop `NOT NULL` on `password_hash` (the model field becomes `str \| None`),… |
| GAP-UNASSIGNED-09 | Known gap | UNASSIGNED | the CLI hint for `STORAGE_UNAVAILABLE` still says to check that the MongoDB… |

## Items

### GAP-M0-01

kind: Known gap
milestone: M0
source: item 4 of 98

the lane list in `check-lane-coverage.sh` duplicates the selectors in the workflow files and is kept in sync by hand. Reading both from one lanes file is a possible follow-up.

### GAP-M0-02

kind: Known gap
milestone: M0
source: item 17 of 98

`tools/docker-smoke.sh` needs `MSYS_NO_PATHCONV=1` on Windows Git Bash, and fails if another process holds host port 8000. Exporting the variable in the script, and using a free host port, are candidate small follow-ups.

### GAP-M1-01

kind: Known gap
milestone: M1
source: item 6 of 98

PR #53 and PR #54 were both merged with a merge commit, so their intermediate commits are on `main`. Those between a contract change and the test updates are not individually green; PR #54 included a CLI test fix that landed after CI caught it. The PR was the green unit each time. Setting the repository to allow squash merges only would stop this for M1b onward. PR #61 and PR #62 were merged the same way (the commits on `main` are titled "Merge pull request #61" and "#62", merge commits `d433a5a` and `f5f142e`), and so were PR #65 (merge commit `0ab8974`, with its three commits on `main`) and PR #69 (merge commit `919c131`, with its seven commits on `main`), so the setting is still not enforced. PR #75 merged as commit `7bce020` and PR #77 as commit `b0c1f9c`; whether either was squashed is not confirmed here. PR #79 merged as commit `92a6982` with 12 commits; whether it was squashed is not confirmed here either. PR #81 merged as commit `fe4928e` with 7 commits; whether it was squashed is not confirmed here either. PR #87 merged as commit `8c53487` with 6 commits; whether it was squashed is not confirmed here either. PR #89 merged as commit `62c7210` with 6 commits; whether it was squashed is not confirmed here either. PR #91 merged as commit `710539a` with 5 commits; whether it was squashed is not confirmed here either.

### GAP-M1-02

kind: Known gap
milestone: M1
source: item 8 of 98

`created_by` is null on rows written before migration `a3f1c9d2b7e4`. Null means pre-attribution; system writers use explicit values such as `system:pre-auth:api` or `system:seed`. The column has no CHECK constraint and no format validation until M4b. Consider a CHECK constraint on rows after a cutoff date.

### GAP-M1-03

kind: Known gap
milestone: M1
source: item 9 of 98

`audit_events` is append-only by repository convention only (D22). A role with UPDATE or DELETE privilege on the table can alter it, no trigger or privilege revocation prevents that, and the table has no read API, retention policy, index or before and after values.

### GAP-M1-04

kind: Known gap
milestone: M1
source: item 10 of 98

account changes made before migration `41065b2e2190` have no audit row and cannot be backfilled. Until M4b.1 and M4.5.3 the recorded actor is the fixed pre-auth constant, so it identifies the application, not a person.

### GAP-M1-05

kind: Known gap
milestone: M1
source: item 11 of 98

`ty` cannot see calls made through untyped fixtures, so a changed repository contract was caught by failing tests rather than by the type check. The audit is a `git grep` over `.save(` and `.save_many(` plus the integration lanes.

### GAP-M1-06

kind: Known gap
milestone: M1
source: item 12 of 98

a unit test can pass by quietly reaching a developer's local PostgreSQL. CI, which has no usable credentials in the unit lane, caught one such test in PR #54 (a CLI context built without a posting repository). A guard that makes any real connection fail in the unit lane is a possible follow-up.

### GAP-M1-07

kind: Known gap
milestone: M1
source: item 13 of 98

a model change without its migration failed 23 integration tests with a misleading `FrozenInstanceError` raised while an exception passed through `contextlib`, hiding the real "column does not exist" error. The cause in `AppError` has not been inspected. Running `alembic check` locally caught the missing migration; it is not yet part of CI or `tools/pre-push.sh`. Both are candidate follow-ups.

### GAP-M1-08

kind: Known gap (M1b)
milestone: M1
source: item 15 of 98

email format is checked only at registration, by a minimal shape rule (D28). `normalize_email` is still a trim and case fold, and an address stored earlier may not satisfy the shape rule, so login does not apply it.

### GAP-M1-09

kind: Known gap
milestone: M1
source: item 16 of 98

`REQUEST_VALIDATION_ERROR` has no catalog entry in either app. It is used only as a raw error code, and both parity tests exclude it by name.

### GAP-M2-01

kind: Known gap
milestone: M2
source: item 18 of 98

log redaction is key-based only. A secret inside exception text, or interpolated into the `event` string, is not caught, and there is no value-pattern detection (JWT or `Bearer` regexes). `hide_parameters=True` covers SQL parameters only. Re-check at M2.8 and M3.8.

### GAP-M2-02

kind: Known gap
milestone: M2
source: item 19 of 98

the redaction markers match by substring, so hyphenated or cookie-style names (`x-api-key`, `cookie`, `set-cookie`, session ids) are not covered. Decide whether to add markers when the API logs headers (M3.7).

### GAP-M2-03

kind: Known gap
milestone: M2
source: item 20 of 98

`_redact_value` and `coerce_context` have no cycle protection; a cyclic `context` would raise `RecursionError` inside the formatter, which the logging module reports and does not propagate. Unlikely in practice, not tested.

### GAP-M2-04

kind: Known gap
milestone: M2
source: item 21 of 98

monetary-key dropping does not recurse and applies only at the top level of `context`.

### GAP-M2-05

kind: Known gap
milestone: M2
source: item 22 of 98

credential detection in validation errors is name-based (D24): a credential field whose name contains no marker (for example `pwd`) is not masked, and nothing checks real models for the convention (`SecretStr`, a marked name, `hide_input_in_errors=True`). The marker list exists in `trutina.shared.secret` and in observability's processors and is kept in sync by hand, because a test in shared cannot import observability under the stdlib-logging contract. Re-check on the real routes at M3.7.

### GAP-M2-06

kind: Known gap
milestone: M2
source: item 23 of 98

the API 422 body returns Pydantic's `msg`. A credential validator that interpolates the value into its message would leak it; validators must raise through `pydantic_error()`. Not enforced.

### GAP-M2-07

kind: Known gap
milestone: M2
source: item 24 of 98

`redact_input()` has no cycle protection and does not look inside sets, and Click's own usage errors can echo an option value (relevant to M4.5.2).

### GAP-M2-08

kind: Known gap
milestone: M2
source: item 25 of 98

the CLI titles every `AppError` panel "Validation Error", including not-found, conflict and now authentication failures. Cosmetic; needs its own small ticket.

### GAP-M2-09

kind: Constraint on M2.6, met (D30)
milestone: M2
source: item 26 of 98

the CLI formatter lets a `field` key in `AppError.context` override `FIELD_LABELS`, so `AUTH_INVALID_CREDENTIALS` must be raised with an empty context, because a `field="email"` would reveal which half of the credentials was wrong. `PasswordAuthenticator` raises it with an empty context and a unit test fails if a context key is added. Nothing enforces this for a future raise site beyond the CLI tests on the label.

### GAP-M2-10

kind: Known gap
milestone: M2
source: item 27 of 98

`AUTH_THROTTLED` has no CLI field label, so its panel shows the field `unknown`, and the CLI cannot show the retry delay. Cosmetic; a label is a one-line change that also changes the CLI parity test.

### GAP-M2-11

kind: Known gap
milestone: M2
source: item 28 of 98

`Retry-After` is verified at handler level only, and the key `retry_after_seconds` is a literal in the API handler with no shared constant. M2.7 produces it through `AppError.throttled` (D32), but the handler still reads it through a literal; M3.7 and M2.8 close the end-to-end check on a real route (R4).

### GAP-M2-12

kind: Known gap
milestone: M2
source: item 29 of 98

the hasher itself still has no length limit. `RegistrationService` and `PasswordAuthenticator` enforce `MAX_PASSWORD_LENGTH` (D28, D30), but any other caller must apply it, and `normalize_password()`, before hashing.

### GAP-M2-13

kind: Known gap
milestone: M2
source: item 30 of 98

a cancelled caller releases its hash slot while the worker thread finishes, so concurrency can briefly exceed the bound. The hasher is also built for one event loop; the semaphore binds to the first loop that contends for it. No app uses it yet, so behavior across the CLI and API loops is untested.

### GAP-M2-14

kind: Known gap
milestone: M2
source: item 31 of 98

the hasher does not reject weak parameters, and `AuthSettings` validates shape only (D26). Rejecting weak values outside test is API startup validation (M3.6).

### GAP-M2-15

kind: Decided in M2.5 (D28)
milestone: M2
source: item 32 of 98

passwords are normalized with NFKC and then stripped at the edges by `normalize_password()` before hashing. The hasher still encodes UTF-8 as given, so login calls the same function (done in M2.6, D30).

### GAP-M2-16

kind: Constraint on M2.6, met (D30)
milestone: M2
source: item 33 of 98

the dummy hash for the unknown-user path must be made once at startup with `hash()`, so it uses the current parameters, because a hardcoded literal hash stops costing the same as a real verify. `PasswordAuthenticator.create()` does this.

### GAP-M2-17

kind: Known gap
milestone: M2
source: item 34 of 98

the default hashing parameters rest on one 260 ms single-run measurement and a documented source, not on load data. M4c.2 measures them under load and may change the defaults.

### GAP-M2-18

kind: Known gap
milestone: M2
source: item 35 of 98

the attempted email passed to `LoginAttemptRepo` is not length-capped, so junk or very long values are stored as given. `PasswordAuthenticator` caps the email with `MAX_EMAIL_LENGTH` before any lookup but does not call `LoginAttemptRepo` yet, so M2.7 had to record only input that passed that cap, and `ThrottledAuthenticator` does (D31). The repository itself still does not cap.

### GAP-M2-19

kind: Known gap
milestone: M2
source: item 36 of 98

`login_attempts` holds attempted addresses in plain normalized form, including addresses that belong to no user. Retention is bounded only by the purge tool and `ThrottledAuthenticator`'s opportunistic purge (M2.7).

### GAP-M2-20

kind: Known gap
milestone: M2
source: item 37 of 98

a naive datetime passed to `LoginAttemptRepo` is the caller's bug and is not guarded. Auth times must stay aware UTC and never be compared with naive posting dates.

### GAP-M2-21

kind: Known gap
milestone: M2
source: item 38 of 98

`tools/purge-login-attempts.py` has no automated test and sits outside `ty` and the lane-coverage script. It was verified by one manual run against seeded rows.

### GAP-M2-22

kind: Known gap
milestone: M2
source: item 39 of 98

the API Docker runtime image copies `packages/` and `apps/api/` only, so `tools/purge-login-attempts.py` runs from a workspace checkout, not from the image. A purge path inside the image is needed before the first deploy at M5.

### GAP-M2-23

kind: Decided at the service in M2.5 (D29), open for routes
milestone: M2
source: item 40 of 98

`RegistrationService` passes `DUPLICATE_USER_EMAIL` to its caller, which reveals which emails are registered, and a duplicate is rejected faster than a new registration. Nothing exposes the service today; whether public registration exists is decided in M5.6.

### GAP-M2-24

kind: Known gap
milestone: M2
source: item 41 of 98

nothing wires `RegistrationService`, `PasswordAuthenticator`, `ThrottledAuthenticator` or `SessionService` into an app, and no route or command calls any of them. All are tested against fakes only; the real-PostgreSQL register, login and throttle check was done in M2.8 and the session service's in M3.4; route-level checks close in M3.7 and M3.8 (R4).

### GAP-M2-25

kind: Known gap
milestone: M2
source: item 42 of 98

`PasswordAuthenticator` rejects blank and over-limit input faster than a wrong password, because it skips hashing. The limits do not depend on any account, so this reveals nothing about one.

### GAP-M2-26

kind: Known gap
milestone: M2
source: item 43 of 98

a rehash write failure fails the login (D30). The rehash is also an unconditional write, so a concurrent password change could be overwritten; accepted because no password-change feature exists. Revisit when a rehash event exists; M2.7 wired only `auth.login_throttled`.

### GAP-M2-27

kind: Known gap
milestone: M2
source: item 44 of 98

the dummy hash is made once per process, so a later change to the hasher parameters leaves it at the old cost until the process restarts.

### GAP-M2-28

kind: Known gap
milestone: M2
source: item 45 of 98

even with throttling (M2.7), every attempt below the limit holds one of the hasher's concurrency slots (default 4), so a burst of attempts queues behind them. A throttled attempt skips hashing; M4c.2 measures the rest.

### GAP-M2-29

kind: Known gap
milestone: M2
source: item 46 of 98

the manual negative checks for M2.6 (dummy verify removed; a `field` key added to the context) are not recorded as run, as for M2.5.

### GAP-M2-30

kind: Known gap
milestone: M2
source: item 47 of 98

passwords are checked for length only (no complexity rule, no breached-password check), and the email check is shape only (no deliverability check, no verification email).

### GAP-M2-31

kind: Known gap
milestone: M2
source: item 48 of 98

the registration duplicate pre-check and the insert are not atomic. The `uq_users_email` index decides a race, and its error passes through unchanged (accepted, as for `AccountService`).

### GAP-M2-32

kind: Constraint on M2.6, met (D30)
milestone: M2
source: item 49 of 98

the minimum password length and the email shape check are registration-only and deliberately not exported. `PasswordAuthenticator` applies neither and treats over-limit input as invalid credentials.

### GAP-M2-33

kind: Constraint from M2.4, met (D31)
milestone: M2
source: item 51 of 98

the attempted email is recorded only if it passed `MAX_EMAIL_LENGTH`; `ThrottledAuthenticator` skips longer emails entirely. `LoginAttemptRepo` itself still does not cap, so any other caller must.

### GAP-M2-34

kind: Decided in M2.7 (D32)
milestone: M2
source: item 52 of 98

`AppError.throttled` owns the `retry_after_seconds` key. The API handler still reads it through a literal, not a shared constant.

### GAP-M2-35

kind: Known gap
milestone: M2
source: item 53 of 98

the throttle's check and its later record are not atomic, so concurrent attempts can overshoot the limit by the number in flight. Accepted; an atomic increment would need a contract change.

### GAP-M2-36

kind: Known gap
milestone: M2
source: item 54 of 98

throttling is per IP and email only (locked decision 7). One IP trying many emails a few times each, and many IPs against one email, are not throttled. A per-IP or per-email limit would be a new decision.

### GAP-M2-37

kind: Known gap
milestone: M2
source: item 55 of 98

`retry_after_seconds` is the window length, an upper bound, so a client may wait longer than needed. An exact value needs an oldest-failure query, which unfreezes `LoginAttemptRepo`.

### GAP-M2-38

kind: Known gap
milestone: M2
source: item 56 of 98

one `auth.login_throttled` event is emitted per rejected attempt, which is noisy under attack. Revisit with the M3 session events.

### GAP-M2-39

kind: Known gap
milestone: M2
source: item 57 of 98

purge runs only when a failure is recorded, so rows linger if failures stop; `tools/purge-login-attempts.py` remains the fallback. An empty email within the length cap is recorded like any other.

### GAP-M2-40

kind: Known gap
milestone: M2
source: item 58 of 98

the manual negative checks for M2.7 (threshold off by one; the count moved after the inner call) are not recorded as run.

### GAP-M2-41

kind: Known gap
milestone: M2
source: item 59 of 98

the client IP reaching `ThrottledAuthenticator` is whatever the caller passes. Until trusted-proxy resolution (M3.6), behind a proxy it would be the proxy's address, which would throttle all clients behind it together. M3.6 must land before the login route (M3.7).

### GAP-M2-42

kind: Known gap
milestone: M2
source: item 60 of 98

two processes configured with different hash parameters rewrite each other's stored hash, one UPDATE per successful login (found in M2.8). It is harmless and temporary, for example during a rolling deploy.

### GAP-M2-43

kind: Known gap
milestone: M2
source: item 61 of 98

the M2.8 log check uses a stdlib handler because storage tests cannot import `trutina-observability`. The structlog redaction pipeline is covered by its own contract tests, and a real credential flow through it is proven only at the routes (M3.7, M3.8).

### GAP-M2-44

kind: Known gap
milestone: M2
source: item 62 of 98

the manual negative checks for M2.8 (dummy verify removed; threshold off by one; the record moved before the inner call; a `field` key added to the context) are not recorded as run. The M2.8 leak check proves absence of plaintext passwords and stored hashes only, not of emails or IPs, which `login_attempts` stores by design.

### GAP-M3-01

kind: Known gap (ADR 0001)
milestone: M3
source: item 63 of 98

there is no automatic detection of a stolen session token. It works until revoked or expired (API: 24 hours idle, 7 days absolute; CLI: 14 and 30 days). Step-up limits the damage: it can read and draft but cannot post or delete without the password (ADR 0002). An anomaly signal such as a second client IP is not designed.

### GAP-M3-02

kind: Known gap (ADR 0001)
milestone: M3
source: item 64 of 98

every authenticated request, reads included, now needs a database connection, and the default `pool_size` is 1. Tuned in M4c.2 from the numbers M4c.1 records.

### GAP-M3-03

kind: Closed in M3.1 (PR #87)
milestone: M3
source: item 65 of 98

the removal of `signing_keys` and `active_kid` from `AuthSettings`, the token fakes and the token contracts. The code and the authentication and config docs no longer describe the JWT design as pending; the removed names remain only in ADR 0001 and in the config removal note, operator note and tests.

### GAP-M3-04

kind: Known gap (ADR 0001)
milestone: M3
source: item 66 of 98

`last_used_at` is touched at most every 5 minutes, so idle expiry is accurate only to that interval. Concurrent touches are tested in M3.3.

### GAP-M3-05

kind: Known gap (ADR 0001)
milestone: M3
source: item 67 of 98

a session token travels only in the `Authorization` header, so the hyphenated header and cookie-style names in the redaction known gap matter from M3.7. The redaction marker decision is due then.

### GAP-M3-06

kind: Known gap (ADR 0002)
milestone: M3
source: item 68 of 98

a thief holding an `api` token can read data and create draft journal entries until it is revoked or expires, and a draft created that way must be reviewed before anyone posts it. Step-up covers posting and deleting only.

### GAP-M3-07

kind: Known gap (ADR 0002)
milestone: M3
source: item 70 of 98

a wrong password on `/auth/reauth` is a 401 that does not end the session, and the new 403 sits beside M5's permission 403. Clients must key on `error_code`; nothing enforces that.

### GAP-M3-08

kind: Known gap (ADR 0002)
milestone: M3
source: item 71 of 98

revoking a user's other sessions on a password change has no route to attach to (no change-password feature exists, reset is deferred). The rehash after login must not revoke anything. `SessionService.revoke_all_for_user` exists since M3.4 and nothing calls it, so deactivating a user revokes nothing: validation rejects the user's sessions through the `users` join, and reactivating the user makes any unrevoked session valid again. That follows from the lookup and is not tested.

### GAP-M3-09

kind: Known gap (ADR 0002)
milestone: M3
source: item 72 of 98

no cap on sessions per user, and the session purge script (`tools/purge-sessions.py`, added in M3.3) is not in the Docker image, as for `tools/purge-login-attempts.py`; both need an answer before the first deploy at M5.

### GAP-M3-10

kind: Closed in M3.3 (PR #89)
milestone: M3
source: item 74 of 98

the wording gap around `touch`. ADR 0002 section 4 was amended to say the lookup is a read and `touch` is a separate call on its own short session, and the M3.3 card no longer says an adapter touch waits for the interval. One request still makes two short sequential database borrows, by design (D36, D37).

### GAP-M3-11

kind: Known gap (M3.1)
milestone: M3
source: item 75 of 98

`PostgresSettings.pool_timeout_s` is declared and not passed to the engine, and how a pool-wait timeout maps to an `ErrorCode` is not confirmed. Not wired in M3.3 (D37): its one-connection pool test builds its own engine with an explicit pool timeout. The wiring is assigned to no ticket yet: before M3.6, whose pool-limit test would otherwise wait for the library default, or in M4c.2.

### GAP-M3-12

kind: Known gap (M3.1)
milestone: M3
source: item 76 of 98

the session lifetime settings have no upper bound and an idle value above its absolute value is accepted (harmless because idle expiry is capped by absolute expiry). Whether to bound them is a new decision.

### GAP-M3-13

kind: Known gap (M3.1)
milestone: M3
source: item 77 of 98

a duplicate session token hash was undefined in `SessionRepo`; since M3.3 the `create` docstring and `PostgresSessionRepo` define it (`UNKNOWN_ERROR`, the violated constraint name only, no cause; D37). A naive datetime passed to `SessionRepo` is still a caller bug and is not guarded.

### GAP-M3-14

kind: Known gap (M3.1)
milestone: M3
source: item 78 of 98

a leftover `TRUTINA_AUTH__SIGNING_KEYS__*` or `TRUTINA_AUTH__ACTIVE_KID` value is ignored silently, with no warning to the operator. Tests pin the behavior; the config README states it.

### GAP-M3-15

kind: Known gap (M3.1)
milestone: M3
source: item 79 of 98

`FakeSessionRepo` stands in for the join to `users` with a `FakeUserRepo`. The real join and the concurrency behavior of touch are now exercised against PostgreSQL by the M3.3 integration tests. The adapter adds a foreign key, so a session for a nonexistent user can exist in the fake and cannot in PostgreSQL.

### GAP-M3-16

kind: Closed in M3.4 (PR #91)
milestone: M3
source: item 80 of 98

the missing automatic purge of `sessions`. `SessionService` deletes sessions dead longer than its retention window on every login, in one unbounded call (D38), and `tools/purge-sessions.py` is still run by hand. The cost of that call is a new known gap (M3.4).

### GAP-M3-17

kind: Known gap (M3.3)
milestone: M3
source: item 81 of 98

`tools/purge-sessions.py` has no automated test and sits outside `ty` and the lane-coverage script, and a manual run against seeded rows is not recorded here.

### GAP-M3-18

kind: Known gap (M3.3)
milestone: M3
source: item 82 of 98

`touch` and `mark_reauthenticated` do not re-check expiry (the contract no-ops only an unknown or revoked session), so the service must call them only after `get_valid` succeeded. `SessionService` does so since M3.4 (it touches only after a successful lookup); any other caller must too.

### GAP-M3-19

kind: Known gap (M3.3)
milestone: M3
source: item 83 of 98

the expiry columns of `sessions` are not indexed, so `purge_before` scans the table. Acceptable while it is small; revisited with load data in M4c.2. Since M3.4 the scan runs on every login (D38).

### GAP-M3-20

kind: Known gap (M3.3)
milestone: M3
source: item 84 of 98

a rejected `create` reports only the violated constraint name, with no driver text and no cause, so diagnosing one rests on that name alone.

### GAP-M3-21

kind: Known gap (M3.3)
milestone: M3
source: item 85 of 98

tests for a bad `client_kind` rejected by PostgreSQL, a reactivated user's session becoming valid again, revoking a mix of `api` and `cli` sessions, and the one-statement lookup are not recorded here.

### GAP-M3-22

kind: Known gap (M3.3)
milestone: M3
source: item 86 of 98

the manual negative checks, the `git grep` audit of every `SessionRepo` implementer and caller, and a local run of `tools/docker-smoke.sh` are not recorded as run (CI's QG7 passed).

### GAP-M3-23

kind: Known gap (M3.4)
milestone: M3
source: item 90 of 98

`SessionService` purges on every login with one unbounded `DELETE` (D38). `sessions` has no expiry-column indexes, so each login scans the table. Not measured; M4c.2 decides whether to batch it or index it.

### GAP-M3-24

kind: Known gap (M3.4)
milestone: M3
source: item 91 of 98

re-authentication goes through `ThrottledAuthenticator`, so a failed re-authentication counts toward the same IP and email as a failed login. With an unresolved client IP (`"unknown"`) a flood of failed re-authentications can throttle that email's login, and the reverse.

### GAP-M3-25

kind: Known gap (M3.4)
milestone: M3
source: item 92 of 98

the revoke-all event is `auth.session_revoked` with `client_kind` set to `"all"`. ADR 0002 names no such kind, and the owner has not confirmed it.

### GAP-M3-26

kind: Known gap (M3.4)
milestone: M3
source: item 93 of 98

the `cli` kind being exempt from step-up is a caller convention. `require_recent_auth` does not check the client kind and no test covers the exemption.

### GAP-M3-27

kind: Known gap (M3.4)
milestone: M3
source: item 94 of 98

edge behaviors of the service. Logout of an expired but unrevoked token is a no-op, so that row stays until a purge. A failed touch fails the request. `validate` returns the session as read, before its touch. A token factory other than the default is a test hook with no guard.

### GAP-M3-28

kind: Known gap (M3.4)
milestone: M3
source: item 95 of 98

`sessions/service.py` imports `credentials` (`Authenticator`, `UserRepo`) by submodule path. `credentials` never imports `sessions`. This is an observed convention, not an import-linter contract.

### GAP-M3-29

kind: Known gap (M3.4)
milestone: M3
source: item 96 of 98

tests not written for `repr` and `str` of the validation result, for logout of an expired token, for the default token factory (43 characters, 32 bytes), for the `cli` exemption, and for a catalog entry removed (none of the five manual negative checks removes one). The stored hash made by the real hasher is not asserted absent from logs, events and error contexts.

### GAP-M3-30

kind: Known gap (M3.4)
milestone: M3
source: item 97 of 98

the existing handler and boundary tests that parametrize over auth codes (`test_handlers.py`, `test_error_boundary.py`) cover only `AUTH_INVALID_CREDENTIALS` and `AUTH_THROTTLED`, not the two new codes.

### GAP-M3-31

kind: Known gap (M3.4)
milestone: M3
source: item 98 of 98

verification not recorded here: per-test output of the manual negative checks (the owner reported that all five failed as expected), a local run of the whole `infra postgres` lane after the final commit, a local `tools/docker-smoke.sh` run (CI's QG7 passed), and what commit `bc081dd` changed beyond its subject. The local results in the ticket card were run before the last commits and not at the merge commit.

### GAP-M4-01

kind: At M4c
milestone: M4
source: item 1 of 98

write down expected load, measure a baseline, revise the provisional thresholds once, then freeze them.

### GAP-M4-5-01

kind: At M4.5
milestone: M4-5
source: item 2 of 98

the CLI session path, whose table, `cli` kind and lifetimes are decided in ADR 0001 and ADR 0002.

### GAP-M5-01

kind: At M5
milestone: M5
source: item 3 of 98

the permission matrix, whether read routes load the access state per request (settled by ADR 0001: yes, session validation already does), and whether single-tenant needs revisiting.

### GAP-UNASSIGNED-01

kind: Deferred
milestone: UNASSIGNED (owner review)
source: item 5 of 98

password reset and the email provider, OAuth, MFA, email verification, API keys, admin UI, an API-client CLI.

### GAP-UNASSIGNED-02

kind: Known gap until reset ships
milestone: UNASSIGNED (owner review)
source: item 7 of 98

a locked-out user has no self-service recovery. Record it in the authentication package's CONTEXT.md.

### GAP-UNASSIGNED-03

kind: Known gap
milestone: UNASSIGNED (owner review)
source: item 14 of 98

the empty revision `7e1b970f05a7` ("check") remains in the migration history. It is a no-op and is left alone in case a database has it stamped.

### GAP-UNASSIGNED-04

kind: Known gap
milestone: UNASSIGNED (owner review)
source: item 50 of 98

PR #75's commits mix the scopes `auth` and `authentication`, and no list of accepted commit scopes is recorded. PR #77's commits use `auth`, and two of its docs commits (`fce85d8` and `6bf3a90`) share one subject. Record one list in the commit conventions. PR #79's commits mix the scopes again, and one uses a file name, `purge-login-attempts`, as its scope. PR #81's commits use the scopes `storage`, `auth` and `config`. PR #91's commits use the scopes `shared`, `authentication` and `storage`, one has no scope, and one subject names a file (`CONTEXT.md`).

### GAP-UNASSIGNED-05

kind: Open (ADR 0002)
milestone: UNASSIGNED (owner review)
source: item 69 of 98

whether account update, which can change the category and so the normal-balance side, needs step-up. Decide in M4a.2 or in the M5.0 matrix.

### GAP-UNASSIGNED-06

kind: Deferred (ADR 0002)
milestone: UNASSIGNED (owner review)
source: item 73 of 98

cookie transport, the Origin check, CORS, CSP and cookie redaction markers wait for ADR 0003, and no web client ships before it. Session metadata (user agent, IP) is deferred until something reads it.

### GAP-UNASSIGNED-07

kind: Known gap
milestone: UNASSIGNED (owner review)
source: item 87 of 98

the merge commit for PR #83 (ADR 0001, M3.0) is not recorded here yet, and neither are M2.2's PR number and merge commit. Whether PR #83 was squashed is not confirmed.

### GAP-UNASSIGNED-08

kind: Deferred to the OAuth milestone
milestone: UNASSIGNED (owner review)
source: item 88 of 98

drop `NOT NULL` on `password_hash` (the model field becomes `str | None`), add `external_identities`, and decide how an OAuth login whose email matches an existing account is treated (linking on an unverified email is an account-takeover risk).

### GAP-UNASSIGNED-09

kind: Known gap
milestone: UNASSIGNED (owner review)
source: item 89 of 98

the CLI hint for `STORAGE_UNAVAILABLE` still says to check that the MongoDB server is running, which is stale since the PostgreSQL cutover. Fix as its own small PR.
