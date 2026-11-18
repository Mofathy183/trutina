# Decisions

## Index

| ID   | Summary                                                                     | Status     |
| ---- | --------------------------------------------------------------------------- | ---------- |
| LD1  | Single-tenant; repository contracts take scalar parameters only             | Active     |
| LD2  | Keyword-only actor parameter required on write services                     | Active     |
| LD3  | Refresh-token table shape deferred until after the D1 ADR                   | Superseded |
| LD4  | Account bootstrap moves to M5 together with roles                           | Active     |
| LD5  | Disabled-flag check on every write, 15-minute token TTL                     | Active     |
| LD6  | Password reset and email deferred past core auth                            | Active     |
| LD7  | App-level login rate limiting                                               | Active     |
| LD8  | AuthSettings skeleton in M0b; fields land per milestone                     | Active     |
| LD9  | CLI uses in-terminal login without browser or URL                           | Active     |
| LD10 | Atomic refresh-token rotation with concurrency test, kept as history        | Superseded |
| LD11 | AuthEventSink stub                                                          | Active     |
| LD12 | Auth routes built in M3 and public                                          | Active     |
| LD13 | Auth CLI command group                                                      | Active     |
| P1   | Deploy gate: API refuses to start without a registered policy               | Active     |
| P2   | Identity dataclass lives inside trutina-authentication                      | Active     |
| P3   | Status checker returns an access-state object                               | Active     |
| P4   | Separate plain SHA-256 token hasher                                         | Active     |
| P5   | CLI never holds signing keys; sessions opaque and database-backed           | Active     |
| P6   | Actor attribution on account writes, as M1c                                 | Active     |
| P7   | Docs routes public in dev and test only                                     | Active     |
| P8   | JWT token TTLs, HS256 key handling and rotation plan                        | Superseded |
| D1   | One opaque database-backed session mechanism for API and CLI                | Active     |
| D2   | environment defaults to production; no auth-off mode                        | Active     |
| D3   | Account audit via audit_events table, not a column                          | Active     |
| D4   | Core checks non-blank actor only; format checks live in apps                | Active     |
| D5   | audit_events is Postgres-only after Mongo retirement                        | Active     |
| D6   | Signing keys validated at API startup, not root Settings                    | Superseded |
| D7   | Test markers derive from repo-relative package prefix table                 | Active     |
| D8   | Empty marker selection fails CI; lane coverage script enforced              | Active     |
| D9   | TestSettings does not override environment; test namespace opts in          | Active     |
| D10  | M0b authentication contract shapes for hasher, clock, verifier and rotation | Active     |
| D11  | Intra-package imports use sibling submodule paths in authentication         | Active     |
| D12  | Blank-actor check lives in trutina-shared rule helpers                      | Active     |
| D13  | Each app owns a fixed pre-auth actor constant                               | Active     |
| D14  | MongoDB storage adapter retired; PostgreSQL only                            | Superseded |
| D15  | Repo contracts take keyword-only created_by; nullable entry/posting columns | Active     |
| D16  | Email stored once, normalized on write, single unique column                | Active     |
| D17  | User.created_at is database-authoritative; caller values ignored            | Active     |
| D18  | set_active exists from M1b; unknown users raise UNKNOWN_USER                | Active     |
| D19  | New DUPLICATE_USER_EMAIL and UNKNOWN_USER codes with parity tests           | Active     |
| D20  | users.password_hash stays NOT NULL until OAuth exists                       | Active     |
| D21  | audit_events table shape: minimal columns, CHECK constraint                 | Active     |
| D22  | audit_events append-only by convention; enforcement deferred                | Active     |
| D23  | Key-based recursive log redaction at every level                            | Active     |
| D24  | Key-based credential masking where FieldViolation.value is built            | Active     |
| D25  | AUTH_INVALID_CREDENTIALS and AUTH_THROTTLED codes with shared messages      | Active     |
| D26  | Argon2id password hashing via argon2-cffi with explicit parameters          | Active     |
| D27  | login_attempts table shape with IP and normalized email keys                | Active     |
| D28  | Password and email input rules for registration and login                   | Active     |
| D29  | RegistrationService shape, ordering and violation reporting                 | Active     |
| D30  | PasswordAuthenticator shape with indistinguishable failures                 | Active     |
| D31  | ThrottledAuthenticator sliding-window throttle keyed on IP and email        | Active     |
| D32  | AppError.throttled constructor owns retry-after rule                        | Active     |
| D33  | End-to-end credential integration tests live in storage-postgres            | Active     |
| D34  | Opaque database-backed sessions replace JWT everywhere (ADR 0001)           | Active     |
| D35  | Per-client-kind lifetimes, step-up reauthentication, connection borrowing   | Active     |
| D36  | Session contracts and settings shape frozen in M3.1                         | Active     |
| D37  | PostgresSessionRepo and sessions table shape in M3.3                        | Active     |
| D38  | SessionService login, validation, reauth and logout shape in M3.4           | Active     |

---

### LD1

**Decision:** Single-tenant; repo contracts take scalar params only

**Why:** No requirement today; a future `tenant_id` is one more opaque parameter

### LD2

**Decision:** Required keyword-only `actor: str` on write services, `created_by` in M1a

**Why:** Forgetting it is a type error, not a silent null. Historical rows cannot be backfilled later. Stays off the frozen domain schemas

### LD3

**Decision:** Superseded by D34 (ADR 0001): no refresh-token table exists. Kept as history: `family_id` in the M3 refresh-token migration, after the D1 ADR

**Why:** No live database or sessions exist before M3, so waiting costs nothing, and the table shape should not be locked before D1

### LD4

**Decision:** Bootstrap moves to M5 with roles

**Why:** No role-less throwaway command; no public register route until then

### LD5

**Decision:** DB disabled-flag check on every write, 15 minute token TTL, reads stateless (superseded by D34: every authenticated request checks the database and there is no token TTL)

**Why:** Closes "disabled user can post" with no cache to keep consistent

### LD6

**Decision:** Password reset and email deferred past core auth

**Why:** Removes an external dependency from the critical path

### LD7

**Decision:** App-level login rate limiting

**Why:** Infra cannot see per-email failures

### LD8

**Decision:** `AuthSettings` skeleton in M0b; fields land in the milestone that needs them

**Why:** No structural settings PR per milestone

### LD9

**Decision:** CLI: in-terminal login, no browser or URL, attribution-only for now

**Why:** No identity provider or web login page exists. Revisit if the CLI is used by anyone who should not hold DB credentials, or if M5 rules must be enforced there

### LD10

**Decision:** Superseded by D34 (ADR 0001): the rotation types were removed in M3.1. Kept as history: atomic rotation plus concurrency test

**Why:** Reuse detection has a hole otherwise

### LD11

**Decision:** `AuthEventSink` stub

**Why:** Logging hooks exist before the observability plan does

### LD12

**Decision:** Auth routes in M3, public

**Why:** They have no purpose before tokens exist

### LD13

**Decision:** `auth` CLI group

**Why:** Matches existing groups; registered groups dispatch one-shot correctly

---

### P1

**Decision:** Deploy gate: outside dev and test the API refuses to start until a policy is registered. There is no auth-disabled mode

**Why:** Otherwise M4 to M5 has every authenticated user acting as admin

### P2

**Decision:** `Identity` inside `trutina-authentication`

**Why:** One frozen dataclass does not justify a package, CI lane and linter layer

### P3

**Decision:** Status checker returns an access-state object

**Why:** M5 needs role on the same per-write query; avoids changing every write path later

### P4

**Decision:** Separate token hasher, plain SHA-256 (named `RefreshTokenHasher` until M3.1, now `SessionTokenHasher`, D36)

**Why:** Lookup needs a deterministic hash; tokens are 256-bit random, so a pepper adds only another secret

### P5

**Decision:** CLI never holds the signing key; sessions are opaque and database-backed

**Why:** A CLI that signs JWTs can forge any API identity. Table shape deferred to M4.5

### P6

**Decision:** Actor on account writes, as M1c

**Why:** Hard-deleting accounts without an audit trail is a gap, and every API write route passes an actor

### P7

**Decision:** Docs routes public in dev and test, disabled elsewhere

**Why:** FastAPI serves them by default; the allowlist must be explicit and conditional

### P8

**Decision:** Superseded by D34 (ADR 0001); kept as history: 15 minute TTL; HS256 with a 256-bit key, algorithm pinned; refresh 14 days idle and 30 days absolute; `kid` and dual-key verify from M3; key-rotation ADR before M3; owner: you. M4c thresholds stay provisional until measured

**Why:** See the next section

---

### D1

**Decision:** Settled (v3.24, ADR 0001, D34): one opaque, database-backed session mechanism for API and CLI

**Why:** The API already hits the database on every write and the CLI needs opaque sessions anyway. Settled in ADR 0001 (docs/adr/0001-session-mechanism.md)

### D2

**Decision:** `environment` defaults to production; no auth-off mode

**Why:** Forgetting one variable must never open `/docs` or skip the gate

### D3

**Decision:** Account audit via `audit_events`, not a column

**Why:** Hard deletes leave no row to hold attribution

### D4

**Decision:** Core checks non-blank only. The actor format check lives in the API and CLI handlers and lands at M4b; until then handlers pass a fixed constant

**Why:** Keeps core free of identity knowledge; a validator on a trusted constant guards nothing

### D5

**Decision:** `audit_events` Postgres-only. Mongo was retired (D14 superseded)

**Why:** New features target PostgreSQL only

### D6

**Decision:** Signing keys validated at API startup, not on root `Settings`

**Why:** Alembic, the CLI and tooling must start without keys (P5)

### D7

**Decision:** Test layer and backend markers derive from a repo-relative `_PACKAGE_MARKERS` prefix table; hand-written derived markers and unmapped paths fail collection

**Why:** Matching any segment of the absolute path could mislabel tests by checkout location. One table means one line per new package

### D8

**Decision:** An empty marker selection fails CI unless the step passes `--allow-empty`; `check-lane-coverage.sh` fails if any test belongs to no lane

**Why:** A mistyped selector or stripped marker otherwise passes with zero tests, and an unselected test never runs

### D9

**Decision:** `TestSettings` does not override `environment`; the test namespace opts in with `TRUTINA_TEST_ENVIRONMENT=test`

**Why:** Matches D2 (default production, opt-in). CI has no `.env.test`, so the test-layer workflows set the variable themselves

---

### D10

**Decision:** M0b contract shapes: `PasswordHasher` is async and owns offloading and its concurrency bound; `Clock` returns timezone-aware UTC; `TokenVerifier` returns `Identity | None`; an unknown user has `is_active=False`; refresh rotation is atomic in the repository and returns an outcome, while the grace window and family revocation stay in the service (the token verifier and refresh rotation parts are superseded by D34 and were removed in M3.1)

**Why:** No caller can forget offloading; auth times never mix with the naive accounting dates; an invalid token is an expected outcome and needs no error code yet; one branch instead of two; adapters hold no policy

### D11

**Decision:** Inside `trutina.authentication`, imports across folders use the sibling's submodule path (`trutina.authentication.identity`), never the package root; imports within a folder stay relative

**Why:** Importing a name from the root while the root `__init__` is still running raises a circular-import error. Found when the tests were first run in the repo

### D12

**Decision:** The blank-actor check lives in `trutina-shared`: `is_non_blank_actor()` in `rule.py` (presence only, never format) and `ValidationAppError.required_field()`, which raises `REQUIRED_FIELD` on `actor` with no new `ErrorCode`. Each write service calls it as its first statement

**Why:** Journal, posting and (M1c) account writes all need it. First position means a blank actor consumes no journal number and takes precedence over unknown-account and unknown-journal errors. `REQUIRED_FIELD` is Pydantic's "missing", and a blank string is not strictly missing; accepted as the closest stable identity

### D13

**Decision:** Each app owns its fixed pre-auth constant: `system:pre-auth:api` in `api/shared/actor.py`, `system:pre-auth:cli` in `cli/composition/actor.py`. Tests share `TEST_ACTOR` (`system:test`). Handler signatures are unchanged until M4b

**Why:** Apps never import each other. Distinct values because `created_by` will store them and pre-auth rows cannot be backfilled, so the writing application stays recoverable. The CLI constant sits with the composition root because `cli/shared/` holds only subpackages and the CLI's real actor will come from its session state

### D14

**Decision:** Superseded: the MongoDB adapter was retired. The `trutina-storage-mongo` package was deleted (issue #60, PR #62, merge commit `f5f142e`) and PostgreSQL is the only storage backend. Earlier decision, kept as history: Mongo was frozen and its journal and posting adapters accepted `created_by` without storing it (M1a)

**Why:** Neither app depended on it, so keeping a backend no feature targets only cost maintenance, and a silent attribution drop made re-wiring it unsafe. Deleting it removes that risk instead of pinning it. M1c.1 had already left its account adapter unchanged by owner decision

### D15

**Decision:** Repo contracts take a required keyword-only `created_by: str`. PostgreSQL stores it as a nullable text column on `journal_entries` and `postings` only, with no foreign key; journal lines inherit their entry's attribution. It stays off the domain schemas and view models, and repository reads never return it

**Why:** A forgotten value is a type error, not a silent null. Lines are written in the entry's transaction, so a per-line column would duplicate it. An opaque string has nothing to reference, and null marks rows that predate attribution, which cannot be backfilled. Keeping it off the frozen schemas leaves the domain unaware of identity (D2)

### D16

**Decision:** Email is stored once, normalized on write: `User.email` is trimmed and case-folded by a validator, `normalize_email()` lives in `trutina-authentication`, and the single unique column is `email` (`uq_users_email`). No `email_key` column. `get_by_email` normalizes its argument

**Why:** A plain unique index on text is case-sensitive, so two casings of one address would both insert. Normalizing at construction makes the invariant hold on every path with no second column and no database `lower()` that could disagree with `casefold()`. The rule belongs with the model that owns it, not in shared. Cost accepted: the original casing is not kept

### D17

**Decision:** `User.created_at` is database-authoritative: stamped by `TimestampedMixin`, read back by `_to_domain()`. A caller-supplied value is ignored by `create()`

**Why:** One source for the timestamp. Storing the passed value would either break the mixin or create two sources that can disagree

### D18

**Decision:** `UserRepo.set_active(user_id, is_active)` exists from M1b. On an unknown user, `set_active` and `update_password_hash` raise `UNKNOWN_USER`

**Why:** Users are never hard-deleted, so deactivation must be possible. Raising a not-found error follows the account repository's precedent; a silent no-op would hide bugs

### D19

**Decision:** New `ErrorCode` members `DUPLICATE_USER_EMAIL` (`user.duplicate_email`, 409) and `UNKNOWN_USER` (`user.unknown`, 404), each with API and CLI catalog entries and the parity test in the same PR. `DUPLICATE_USER_EMAIL` carries no email value in its context

**Why:** A silent `UNKNOWN_ERROR` is the known-gap pattern the journal-number conflict already shows. The context flows into logs and responses, so an email there would write personal data into every failure line

---

### D20

**Decision:** `users.password_hash` stays `NOT NULL` until OAuth exists

**Why:** Dropping the constraint later is a metadata-only migration, while a nullable column now adds an untested login branch. OAuth identities belong in a separate `external_identities` table, not as columns on `users`

### D21

**Decision:** `audit_events` shape: `id` bigint autoincrement, `entity`, `entity_key`, `action`, `actor` (all text, NOT NULL) and `occurred_at` `timestamptz` stamped by PostgreSQL. No foreign key, no `updated_at`, no payload, no indexes. `entity_key` is the account code as a string. `action` is constrained by `ck_audit_events_action`, built from `AuditAction` (`create`, `update`, `delete`). `entity` is free text, written as `account`. One row per successful call, including an update that changes nothing. A rejected audit insert is `UNKNOWN_ERROR` and rolls the write back; no dedicated `ErrorCode` exists. The model and enum live in `storage_postgres/audit/`, with no repository class

**Why:** A delete leaves no row to carry attribution (D3), so the key must outlive the account: no foreign key. The database clock keeps one source for time (as D17), and a table that is never updated needs no `updated_at`. A CHECK built from the enum stops the table drifting from the code. Indexes and payloads wait until something reads the table. Core has no audit concept, so the enum belongs in the storage package

### D22

**Decision:** `audit_events` is append-only by repository convention only. Database-level enforcement (a trigger or revoked privileges) is deferred and recorded as a known gap

**Why:** M1c.2 had to prove attribution and atomicity first. A trigger or a restricted role changes deployment and test setup (the test fixture truncates the table), so it needs its own ticket rather than being folded into this one

### D23

**Decision:** Log redaction is key-based and recursive. A credential-shaped key (`password`, `secret`, `token`, `authorization`, `credential`, `api_key`, matched as a substring of the lower-cased key) is masked whatever its value, at every log level. Dict values are checked under their own keys, list and tuple items under the parent key, and the input is never mutated. Monetary keys keep their separate rule: dropped above DEBUG, top level of `context` only

**Why:** M2 puts passwords and tokens into request-shaped context. Only the outer key was tested before, so a secret one level down leaked, as reproduced in M2.0. Level independence matches the intent that a credential has no safe form at any level

### D24

**Decision:** Credential masking in validation errors is key-based and applied where `FieldViolation.value` is built. A location segment or dict key containing `password`, `secret`, `token`, `authorization`, `credential` or `api_key` (substring, case-insensitive) is masked, a container input is masked recursively, and credential models set `hide_input_in_errors=True`. Domain codes carried in `value` as a code string are not masked

**Why:** The exception carries no model type, so type-based detection is impossible at this choke point. Pydantic reports a whole parent object as the input of a `missing` error, so a name check alone leaks a sibling credential. Over-matching costs a diagnostic; a leak costs far more

### D25

**Decision:** Auth error codes: `AUTH_INVALID_CREDENTIALS` (`auth.invalid_credentials`, 401) and `AUTH_THROTTLED` (`auth.throttled`, 429), in a new Auth group, each with an API catalog entry, CLI `ERRORS` and `HINTS` entries and the parity tests in one PR (the D19 pattern). Messages and hints have no placeholders, and one code covers unknown email, wrong password and a disabled account. The throttle delay travels in `AppError.context["retry_after_seconds"]`, a digits-only string; the API emits `Retry-After` only for a valid value (leading zeros normalized) and otherwise returns the 429 without the header. The CLI labels invalid credentials `credentials` and throttling nothing. Neither code is incident-worthy: both log at INFO and neither is in the CLI `_ERROR_LEVEL_CODES`. No `AppError` constructor yet

**Why:** One shared message and a context-free error make the three failure causes indistinguishable, so responses cannot enumerate accounts. Context is a string mapping, so the delay must be a string; digits-only blocks header injection, and a bad value must never turn a 429 into a handler failure. A single-field label would reveal which half was wrong. M2.7, the first raiser of the throttled code, decides whether a constructor should own the key

### D26

**Decision:** Passwords are hashed with Argon2id through `argon2-cffi` (25.1.0, verified on Python 3.14.4). `Argon2PasswordHasher` takes plain keyword-only `time_cost`, `memory_cost_kib`, `parallelism` and `max_concurrency`, and does not import `trutina-config`; composition roots map `AuthSettings` onto it. Defaults: 3 iterations, 64 MiB, 1 lane, 4 concurrent hashes, above the OWASP Argon2id minimum and consistent with RFC 9106. `AuthSettings` validates only what Argon2 requires (each value at least 1, memory at least 8 KiB and at least 8 KiB per lane). Hashing runs through `asyncio.to_thread` behind a semaphore, one hasher per event loop. `verify` returns `False` and `needs_rehash` returns `True` for a malformed hash. No Unicode normalization and no length limit in the hasher

**Why:** A self-describing hash carries its parameters, so cost can change later without a migration; `pwdlib` only wraps the same library, `bcrypt` truncates at 72 bytes, `passlib` is unmaintained and `scrypt` would need a hash format kept in this repo. Plain constructor values keep authentication free of a config dependency. A malformed hash can never have verified, so the rehash path cannot reach it. Normalization and length are input rules for register and login (M2.5, M2.6), so both paths apply them identically. Strength is a deployment decision, so rejecting weak values in production belongs to startup validation (D6, M3.6). One hash took about 260 ms (single run) and peak hashing memory is about 256 MiB per process at the defaults; M4c.2 revisits all four values with load data

### D27

**Decision:** `login_attempts` shape: `id` bigint autoincrement, `ip` text, `email_key` text and `attempted_at` `timestamptz`, all NOT NULL. No foreign key, no `updated_at`, no timestamp mixin. `email_key` is `normalize_email()` of the attempted address. `attempted_at` is the caller's aware UTC time from `Clock`, not a database default. `ip` is plain text, not `inet`. Indexes: `(ip, email_key, attempted_at)` for count and clear, `attempted_at` for purge. `count_failures` is inclusive of `since`; `purge_before` is strictly older than the cutoff and returns the deleted count; no method raises a domain error. The code lives in `storage_postgres/login_attempt/`, one folder per persisted authentication concern, and `identity/` stays users-only. The contract is in `credentials/login/attempts.py` (moved from `credentials/attempts.py` when M2.5 grouped the credential modules). The purge script `tools/purge-login-attempts.py` takes `--older-than-hours` (default 24) and adds no `AuthSettings` field

**Why:** The attempted address need not belong to a user, so no foreign key. The throttle window is computed from `Clock`, so the stored time must come from it too. `inet` would reject the `"unknown"` sentinel. The indexes follow the three query shapes and are revisited with load data in M4c.2. No scheduler exists, so retention needs a documented tool, and a setting would add configuration before any consumer exists

### D28

**Decision:** Password and email input rules (M2.5). `normalize_password()` converts to NFKC and then strips leading and trailing whitespace; whitespace between characters is kept and case is never changed. Registration and login must both call it. `MAX_PASSWORD_LENGTH` is 128 characters, checked on the raw input and again after normalization. The minimum is 8 after normalization and is registration-only (`MIN_PASSWORD_LENGTH`, not exported); a blank or whitespace-only password is `REQUIRED_FIELD`. `MAX_EMAIL_LENGTH` is 254. The email shape (after `normalize_email`: not empty, no whitespace or control characters, exactly one `@` with text on both sides, at most 254 characters) is checked at registration only, never on `User`. All are constants in authentication, not `AuthSettings` fields

**Why:** One function means registration and login hash the identical string, and changing it after users exist locks them out, so it is decided before any exist. NFKC runs first because it turns the no-break and ideographic spaces into ordinary spaces, which the strip then removes. The raw length check bounds normalization cost and the second check covers NFKC lengthening some characters. The minimum and the shape check are registration-only because login must not reject a user whose credentials predate a rule, and a `User` validator would make stored rows fail to read, as `Account.code` did. Settles the length, normalization and email-format items D26 and M1b left open

### D29

**Decision:** Registration use case shape (M2.5). `RegistrationService` in `credentials/users/` takes a user repo, a hasher, a clock and an optional event sink, and returns `RegisteredUser(id, email)`, never a `User`. Order: validate, normalize, duplicate pre-check, hash, create an active user, emit. The rules are checked in the service and violations are built directly, not raised through Pydantic validators; email and password violations are reported together, the password violation value is the redaction mask and the email value is empty. `DUPLICATE_USER_EMAIL` propagates with `resource` and `field` only, checked before hashing, and a duplicate from `create` in a race passes through unchanged. A failure to build the `User` is `UNKNOWN_ERROR` with the cause attached. One event, `auth.user_registered`, carries `subject_id` only, on success only. New `ErrorCode.INVALID_EMAIL` (`user.invalid_email`, 422) with API and CLI entries and parity tests. `trutina-authentication` depends on `trutina-shared`, and `credentials/` is grouped into `passwords/`, `users/` and `login/`

**Why:** A returned `User` would expose `password_hash`, which Pydantic hides from `repr` but not from `model_dump()`. A domain code raised through a validator is downgraded to `UNKNOWN_ERROR` by `get_field_violations()`, so building violations in the service keeps the real code. A `User` that cannot be built after validation is a server defect, not a caller mistake, so it is not a 422. Duplicate exposure to a public caller waits for M5.6; no caller exists today. The folder grouping keeps each folder at two or more related modules as login and throttling add files

### D30

**Decision:** Login verification shape (M2.6). `PasswordAuthenticator(users, hasher, dummy_hash)` in `credentials/login/` implements `Authenticator` and is built with the async `create()`, which makes the dummy hash once with `hash()` of a random value. Order: raw password cap, `normalize_password()`, email normalization and cap, lookup, verify (against the dummy hash for an unknown email), `is_active`, rehash, `Identity`. Unknown email, wrong password, disabled account, blank password and over-limit input raise one `AUTH_INVALID_CREDENTIALS` with an empty context. Blank and over-limit input is rejected before any lookup or hash. Verification runs before the disabled check. A stale hash is replaced after a successful login of an active user, and a storage error from that write propagates unchanged. No `Clock`, event sink or throttling; `client_ip` is accepted and unused

**Why:** One error and an empty context make the causes indistinguishable and stop account enumeration (D25); the CLI formatter lets a `field` key override the label. An unknown email must cost a real verify, so the dummy hash comes from `hash()` with current parameters, and verify precedes the disabled check for the same reason. Hashing unbounded input is a denial-of-service lever, so limits apply first; they do not depend on any account, so the faster return leaks nothing about one. The minimum length and the shape check are registration-only (D28). A rehash that cannot persist is a storage incident, so it is not swallowed. Time, events and the client IP belong to throttling (M2.7)

### D31

**Decision:** Login throttling shape (M2.7). `ThrottledAuthenticator` in `credentials/login/` wraps any `Authenticator` and takes plain keyword-only `max_failures` and `window_seconds` (both at least 1) plus an inner authenticator, a `LoginAttemptRepo`, a `Clock` and an optional event sink; `AuthSettings` gains `login_max_failures` (5) and `login_window_seconds` (900), validated for shape only. Sliding window keyed on IP and normalized email; throttled when the count in the window is at least the limit, checked before the inner call. Counts every `AUTH_INVALID_CREDENTIALS` from the inner authenticator and nothing else; skips an email over `MAX_EMAIL_LENGTH` entirely; never records a throttled attempt. A missing IP is `"unknown"`. Clear on success only if failures were counted. Opportunistic purge of rows older than the window after each recorded failure, with no per-process state. Attempt-store errors propagate unchanged (fail closed). `retry_after_seconds` is the window length

**Why:** A decorator leaves `PasswordAuthenticator`'s tested, indistinguishable-failure properties untouched. Counting before the inner call, keyed without reference to the account, makes unknown and known emails behave identically and spares the hasher during an attack. Not recording throttled attempts keeps the retry bound true and stops a retrying client extending its own delay. The email cap keeps junk out of storage (the M2.4 constraint). A failed record or purge is a storage incident, as for a failed rehash (D30), so it is not swallowed. A stateless purge keeps `Container`'s services stateless, and its cost is negligible beside the verify a failure already paid. The frozen contract has no oldest-failure query, so the window is the only honest bound. Clearing only when needed saves a DELETE on every ordinary login

### D32

**Decision:** `AppError.throttled(retry_after_seconds)` in `trutina-shared` builds `AUTH_THROTTLED` with `context["retry_after_seconds"]` as `str(max(value, 0))`. The only event is `auth.login_throttled`, one per rejected attempt, with `retry_after_seconds` as its only context and no email or IP

**Why:** Closes the question D25 left to M2.7: one constructor owns the digits-only string rule instead of every raiser formatting it, and a clamped non-negative integer can never fail the API's header check. Email and IP are personal data and the event reaches logs. No event for ordinary failures keeps the stream to incidents

### D33

**Decision:** End-to-end credential verification lives in `trutina-storage-postgres` (`shared/tests/test_credentials_integration.py`), not in authentication or core. It uses the real hasher with the cheapest parameters, a recording subclass of it, a `FakeClock` and a fake event sink, and a stdlib log handler with a positive control. Its wiring stays module-local until a second consumer (M3.8) needs it

**Why:** Authentication may not import storage, core may not import either, and storage tests may not import `trutina-observability`, so storage is the only layer that can hold both repositories. A real hasher is the only way to show a real hash carries no plaintext. A fake clock keeps the window deterministic because `attempted_at` is caller-supplied (D27). A caplog check can miss records from async tests under the session loop and pass vacuously, so a direct handler plus a control record is used. Extracting fixtures on the second consumer follows the plan's own rule

### D34

**Decision:** One opaque, database-backed session mechanism for API and CLI (ADR 0001), settling D1. A 256-bit CSPRNG token is sent as `Authorization: Bearer` and only its SHA-256 hash is stored, through the P4 hasher port. One query per authenticated request joins the session to the user and requires not revoked, idle expiry and absolute expiry in the future, and `is_active`. Lifetimes 14 days idle, 30 days absolute (refined per client kind by ADR 0002, D35), with `last_used_at` touched at most every 5 minutes. No rotation, no refresh route, no cookies, no signing keys. Logout revokes one session; password change and deactivation revoke all of a user's sessions. API and CLI share one table with a client-kind column. Supersedes P8, D6 and the JWT parts of M3; `AUTH_REFRESH_CONFLICT` is dropped

**Why:** The API already reads the database on every write (decision 5) and the CLI needs opaque sessions anyway (P5), so JWT would add a second mechanism, signing keys and rotation without removing a lookup that writes already pay. Revocation takes effect on the next request, which matters for financial data, and the 15-minute read window disappears. Accepted costs: a database round trip on every authenticated request, so pool sizing becomes real (M4c.1 pulled forward, M4c.2); no automatic theft detection, only bounded lifetimes and instant revoke. Revisit if a second service must verify tokens without the database, if measured lookup p95 stays above the M4c.2 target after tuning, or if a browser or third-party client needs delegated tokens

### D35

**Decision:** Sessions (ADR 0002, amends ADR 0001). Strict client kinds `api` and `cli` (CHECK); a session is valid only for its kind, `get_valid` takes the kind. Lifetimes per kind as `AuthSettings` fields: `api` 24 hours idle and 7 days absolute, `cli` 14 and 30 days, provisional until M4c.2; `idle_expires_at = min(now + idle, absolute)`; touch at most every 300 seconds. Step-up: `authenticated_at` and a fixed 30-minute window (`reauth_window_minutes`) on `POST /postings/{journal_number}`, account delete and later user and role management; none for reads, journal entry creation or the CLI. New `AUTH_REAUTH_REQUIRED` (`auth.reauth_required`, 403, empty context) with API and CLI entries and parity. `POST /auth/reauth` takes a password only, goes through `ThrottledAuthenticator`, does not rotate the token and leaves the session valid on failure; `GET /auth/me` reports the session. Borrow, use, return: the session lookup uses its own short connection, no request nests sessions, no connection is held while hashing, and `PostgresSettings.pool_timeout_s` is explicit. Dead sessions older than 7 days are purged by a tool script and a bounded batch (the batch part is superseded by D38: the purge on login is one unbounded call). Events carry `subject_id` and `client_kind` only. Bearer stays; cookies, Origin check, CORS and CSP wait for ADR 0003, and no web client ships before it

**Why:** One lifetime pair gave a remote client an operator-length session. A shared kind check would let a leaked 30-day CLI token act through the network API. ADR 0001 accepted no theft detection, so step-up limits what a stolen `api` token can do: it can read and draft, but cannot post or delete without the password; the CLI skips it because it already holds the database URI. Holding a connection through the handler needs two connections per request, which deadlocks a pool of 11 under load. Cookies add CSRF surface for a client that does not exist. Lifetime numbers are tunable settings, not architecture. Revisit if a web client is scheduled, lookup p95 misses the M4c.2 target, users find the window disruptive, or the CLI reaches people without database credentials

### D36

**Decision:** Session contract and settings shape (M3.1, under ADR 0001 and ADR 0002). The contracts live in `trutina-authentication`'s `sessions/` folder (renamed from `tokens/`): `ClientKind` (`api`, `cli`), a frozen `SessionRecord` (token hash excluded from `repr`, aware UTC times, `authenticated_at`, idle and absolute expiry, `revoked_at`), `ValidSession` (the record plus `AccessState`) and `SessionRepo`. `get_valid(token_hash, *, client_kind, now)` requires the kind, never writes, and returns `None` for every failure without saying why. `touch` is a separate call: the caller decides when a touch is due and passes the new idle expiry, and the adapter never moves a stored time backward. `touch`, `mark_reauthenticated` and `revoke` are no-ops on a miss, `revoke` is idempotent, and `purge_before(cutoff)` removes sessions that died strictly before the cutoff and returns the count. No method raises a domain error and no policy lives in an adapter. The token hash port is `SessionTokenHasher`. `AuthSettings` has six session fields (24 hours, 7 days, 14 days, 30 days, 300 seconds, 30 minutes), each at least 1 with no upper bound and no idle-versus-absolute check, and `trusted_proxies` (IP or CIDR strings, checked at construction, default empty). `signing_keys` and `active_kid` are removed and leftover variables are ignored. `PostgresSettings.pool_timeout_s` (5.0, greater than 0) is declared and not passed to the engine

**Why:** Frozen now (R5) so M3.3 and M3.4 build against one contract. One `None` for every failure keeps a bad token indistinguishable (D25, D30). Lifetimes, when a touch is due and retention are service policy, as D10, D27 and D31 already require. A separate touch keeps a write out of the read path and each repository method on its own short session (ADR 0002); the cost is two sequential borrows per request, a wider reading of ADR 0002 section 4, recorded as a known gap. The folder holds sessions, so it is named for them. Shape-only validation follows D26 and D31, and a proxy typo should fail at construction instead of leaving a proxy untrusted. `pool_timeout_s` is declared only because wiring it changes failure latency for both apps and how a pool timeout maps to an `ErrorCode` is not confirmed

### D37

**Decision:** Session store shape (M3.3, under ADR 0001, ADR 0002 and D36). `PostgresSessionRepo` and `SessionModel` in `storage_postgres/session/`, over a `sessions` table, migration `5bdeae152b29`. Columns: `id` bigint autoincrement primary key; `token_hash` text NOT NULL, unique (`uq_sessions_token_hash`); `user_id` uuid NOT NULL, foreign key to `users.id` with `ON DELETE RESTRICT` (`fk_sessions_user_id_users`); `client_kind` text NOT NULL with `ck_sessions_client_kind`, built from `ClientKind`; `created_at`, `last_used_at`, `authenticated_at`, `idle_expires_at` and `absolute_expires_at` (`timestamptz`, NOT NULL) and a nullable `revoked_at`. Every time is the caller's aware UTC value, none is a database default, there is no `updated_at` and no CHECK relates the two expiries. Indexes: the unique `token_hash` and `ix_sessions_user_id` only; no expiry-column indexes. `get_valid` is one read-only SELECT joining `users`, with the caller's `now` and strict comparisons. Each write is one UPDATE or DELETE on its own short session: `touch` and `mark_reauthenticated` set `GREATEST(stored, new)`, every update requires `revoked_at IS NULL`, and `purge_before` deletes a session when any of its three end times is strictly before the cutoff. A rejected `create` (duplicate hash or unknown user) raises `UNKNOWN_ERROR` with a context of `resource` and `constraint` only and no `cause`, raised outside the `except` block so the driver exception is not chained. The adapter computes no lifetime and runs no purge of its own; retention is `tools/purge-sessions.py` (`--older-than-days`, default 7, no setting), and the bounded purge on session creation moves to M3.4. `pool_timeout_s` stays unwired

**Why:** A surrogate key matches `audit_events` and `login_attempts` and keeps the hash a plain unique column. RESTRICT because users are never deleted and a cascade would silently destroy rows ADR 0002 keeps for forensics; it also makes an unknown user detectable. A CHECK built from the enum stops the table drifting from the code (D21). Caller-supplied times because expiry is computed from `Clock` (D27). Single statements with `GREATEST` leave no read-modify-write, so concurrent touches cannot shorten a session, and a read-only lookup keeps writes out of the read path (ADR 0002 section 4, amended in M3.3 to say so). A duplicate-key message from the driver can contain the stored value, and a cause reaches the one failure log line, so the error names the constraint only; both cases are defects, not domain outcomes, so no `ErrorCode` is added (D36). Retention is policy, so the purge on creation belongs to the service (D31 precedent) and `purge_before` has no batch limit. Expiry indexes wait for load data (M4c.2): `idle_expires_at` is rewritten on every touch, so an index would defeat heap-only updates, and the purge predicate is an OR across three columns. Wiring `pool_timeout_s` changes failure latency for both apps and how a pool timeout maps to an `ErrorCode` is not confirmed, so it is a separate change

### D38

**Decision:** Session service shape (M3.4, under ADR 0001, ADR 0002, D36 and D37). `SessionService`, `IssuedSession` and `SessionLifetime` live in `trutina-authentication`'s `sessions/service.py`, and `Sha256SessionTokenHasher` (hex SHA-256 of the UTF-8 token, no salt, no pepper) in `sessions/sha256_hasher.py`. The service takes plain keyword-only values and does not import `trutina-config`: a `SessionRepo`, a `UserRepo`, an `Authenticator` (the composition root passes `ThrottledAuthenticator`), a `SessionTokenHasher`, a `Clock`, a `SessionLifetime` (idle and absolute `timedelta`) for every `ClientKind`, `touch_interval`, `reauth_window` and `purge_retention` (each positive, otherwise `ValueError`), an optional event sink and an optional token factory (default `secrets.token_urlsafe(32)`). `login` authenticates first; only a success creates a session. It then makes one `purge_before` call with a cutoff of now minus `purge_retention`, not batched and made before the insert, and stores a record whose `created_at`, `last_used_at` and `authenticated_at` are now and whose `idle_expires_at` is `min(now + idle, absolute)`. It returns `IssuedSession` (`token` as a `SecretStr`, `subject_id`, `client_kind`, `absolute_expires_at`); the raw token exists nowhere else. `validate` rejects a blank token or one over 128 characters without hashing, looks the token up with its client kind, and raises `AppError` with `AUTH_TOKEN_INVALID` and an empty context for every failure (a disabled user included, until M3.5 decides `AUTH_USER_DISABLED`). It records a use with a separate `touch` only when `touch_interval` has passed (inclusive) and returns the `ValidSession` as read, before the touch. `require_recent_auth` is synchronous and exclusive: `authenticated_at` a full `reauth_window` old raises `AUTH_REAUTH_REQUIRED` (empty context); `authenticated_at` is set only by login and re-authentication, and the `cli` exemption is a caller convention, not checked. `reauthenticate` takes its identity from the session: it validates the token, reads the session's user, verifies the password through the authenticator (so through the throttle), then calls `mark_reauthenticated`; it never rotates the token, and a failure leaves the session valid. `logout` is idempotent and bound to the client kind: an unknown, revoked, expired or other-kind token is a silent no-op with no event. `revoke_all_for_user` ends both kinds and emits `auth.session_revoked` with `client_kind` set to `"all"`. Events (`auth.session_created`, `auth.session_revoked`, `auth.session_reauthenticated`) carry `subject_id` and `client_kind` only. New codes `AUTH_TOKEN_INVALID` (`auth.token_invalid`, 401) and `AUTH_REAUTH_REQUIRED` (`auth.reauth_required`, 403), each with an API entry, CLI `ERRORS` and `HINTS` entries, no CLI field label and the parity tests, in one PR (the D19 pattern).

**Why:** Policy belongs to the service and not to an adapter, as D10, D27, D31 and D36 already require. Plain values keep authentication free of a config dependency (D26). One token error with an empty context makes every cause indistinguishable, as D25 and D30 did for credentials. Purging before the insert means a failed purge leaves no orphan session. The purge is unbounded because the frozen `purge_before` has no limit and unfreezing it was out of scope (R5); `sessions` has no expiry-column indexes, so the call scans the table on every login, which M4c.2 revisits with load data (known gap). The exclusive step-up window matches the exclusive expiry rule. Re-authentication goes through the throttle so the route cannot be used to guess passwords (ADR 0002), and its failures share the login counter for the same IP and email (known gap). The service touches only after a successful lookup because the adapter does not re-check expiry. The revoke-all event kind `"all"` was chosen during implementation because the event spans both kinds and ADR 0002 names no other event; it is not confirmed by the owner. Revisit if M4c.2 shows the purge cost matters (batch it or index the expiry columns), if a bad-token cause must be told apart, or if the `cli` kind must be refused by `require_recent_auth` itself.

---

## P8 detail (superseded, kept as history)

**Superseded in v3.24 by ADR 0001 (D34).** There is no JWT, signing key or refresh rotation, so the TTL, key-rotation and algorithm text below no longer applies and is kept as history. With opaque sessions a revoked or disabled session is rejected on the next request, so the read-exposure window below is zero. The residual risk that replaces it is a stolen session token working until it is revoked or expires (at most 24 hours idle or 7 days absolute for an `api` session, 14 and 30 days for a `cli` session; ADR 0002), with no automatic theft detection. Emergency response is a single UPDATE revoking every session.

A JWT cannot be revoked before it expires, so the TTL is the longest a revoked or stolen access token keeps working. Owner: you. Deadline: the ADR before M3 starts. Review at M5, after any auth incident, and when a second service needs to verify tokens.

| Scenario                                | Exposure                                                                               |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| User disabled, then writes              | About zero: decision 5 checks the database on every write                              |
| User disabled or logged out, then reads | Up to 15 minutes; logout revokes the refresh family at once                            |
| Stolen access token                     | Up to 15 minutes of reads; writes only while the account is active                     |
| Stolen refresh token                    | Bounded by rotation and family reuse detection; first reuse revokes the family         |
| Signing key leaked                      | Worst case: forged identities until rotation. The TTL does not help; key handling does |

**Residual risk accepted:** read-only access to financial data for at most 15 minutes after revocation. That is acceptable for a single-tenant system with no authorization rules yet.

### Why 15 minutes

At 5 minutes, refresh load triples for little gain, because writes are already checked against the database. At 60 minutes, the read exposure window quadruples for no operational benefit. At 15 minutes an active client refreshes about 4 times an hour, each one atomic update plus one insert; M4c confirms the cost.

### Key rotation

- **Planned:** add the new key as verify-only, flip signing to it, retire the old key after at least 1 hour of overlap (longer than TTL plus leeway).
- **Emergency:** drop the old key at once. Access tokens die, clients refresh silently, and sessions survive because refresh tokens are opaque and database-backed (P4, P5).
- **Algorithm (locked):** HS256 with a random key of at least 256 bits, and the verifier accepts HS256 only. Revisit trigger: a second service that needs to verify tokens, at which point move to asymmetric signing so verifiers hold only a public key.
- **Refresh lifetime (locked):** 14 days idle (each rotation issues a fresh expiry) and a 30 day absolute cap from the family's creation. Headless `TRUTINA_AUTH_TOKEN` users log in again every 30 days until API keys exist.
- **Key source:** `signing_keys` and `active_kid`, each key at least 32 bytes, placeholders rejected, no defaults, from real environment variables. Rolling deploys ship the new key as verify-only to every instance first, then flip `active_kid`. **Known gap:** `trutina-config` has no secrets-manager integration.
- **Events via `AuthEventSink`:** refresh reuse, login throttling, status-check failures, logged as structured events. Alerting is log-based until a metrics path exists.
