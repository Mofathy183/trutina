# M3 — Sessions

## Milestone record

### M3 — Sessions and auth routes (re-scoped by ADR 0001)

- **M3.0 done**: `docs/adr/0001-session-mechanism.md` written and approved by the owner on 2026-10-30. It settles D1: one opaque, database-backed session mechanism for API and CLI (D34). Issue #82, PR #83, branch `chore/82-token-key-rotation-adr`, merge commit `acbdba4`
- **M3.1 done** (issue #86, PR #87, merge commit `8c53487`, 6 commits, 8 of 8 checks green, branch `feat/86-session-contracts-and-settings` deleted): frozen session contracts in `sessions/` (the folder was `tokens/`), the session and trusted-proxy settings, `PostgresSettings.pool_timeout_s` declared and not read, and the token contracts, token fakes and signing-key settings removed. Contracts and settings only; nothing implements or reads them yet. See the M3.1 ticket card and D36
- **M3.3 done** (issue #88, PR #89, merge commit `62c7210`, 6 commits, 8 of 8 checks green, branch `feat/88-postgres-session-store` deleted): `PostgresSessionRepo` over a `sessions` table with migration `5bdeae152b29`, and `tools/purge-sessions.py`. Nothing calls the adapter yet. See the M3.3 ticket card and D37
- **M3.4 done** (issue #90, PR #91, merge commit `710539a`, 5 commits, 8 of 8 checks green, branch `feat/90-session-service` deleted): `SessionService` and `Sha256SessionTokenHasher` in `trutina-authentication`'s `sessions/` folder, with `AUTH_TOKEN_INVALID` and `AUTH_REAUTH_REQUIRED` and their API and CLI catalog entries. Service only; nothing calls it yet. See the M3.4 ticket card and D38
- Mechanism: a 256-bit random token sent as `Authorization: Bearer`, stored only as a SHA-256 hash through the existing deterministic-hash port (P4), never the password hasher. No cookies, no rotation, no refresh route, no signing keys
- Validation is one query on every authenticated request: session by hash joined to the user, requiring not revoked, idle expiry in the future, absolute expiry in the future and `is_active`. The join supplies `AccessState`, so M5 roles extend it. Times come from `Clock`
- Lifetimes per client kind (ADR 0002, D35): `api` 24 hours idle and 7 days absolute, `cli` 14 days idle and 30 days absolute, provisional defaults held in `AuthSettings`. Idle expiry is `min(now + idle, absolute)`. `last_used_at` is refreshed at most once per touch interval (default 5 minutes)
- Contracts: `SessionRepo` and session models replace `TokenIssuer`, `TokenVerifier`, `AccessToken`, `RefreshTokenRepo` and the rotation types; the token fakes are replaced; `signing_keys` and `active_kid` are removed from `AuthSettings` **(done in M3.1)**
- `PostgresSessionRepo` and a `sessions` migration with a tested downgrade; `clean_pg_db` truncate list updated; a client-kind column so M4.5 reuses the table **(done in M3.3)**
- Session service: login after `ThrottledAuthenticator` succeeds, validate, logout, revoke-all-for-user. A password change or deactivation revokes all of the user's sessions. Adds `AUTH_TOKEN_INVALID`; `AUTH_REFRESH_CONFLICT` is dropped; `AUTH_USER_DISABLED` is decided in M3.5 **(service done in M3.4; no route, and nothing yet revokes on a password change or deactivation)**
- Public routes `POST /auth/login` and `/auth/logout` through the normal Router, Mapper, Handler, Presenter shape; logout is idempotent. 401 responses carry `WWW-Authenticate` (extend `_response_headers`)
- Write routes keep the per-write disabled check (decision 5); it is now the same lookup every authenticated request makes
- Strict client kinds (ADR 0002): `get-valid` takes the kind and a token of the other kind fails as `AUTH_TOKEN_INVALID`. The API validates `api` sessions only
- Step-up (ADR 0002): a session carries `authenticated_at`; posting and account delete require it within a fixed 30-minute window or return 403 `AUTH_REAUTH_REQUIRED`. `POST /auth/reauth` (password only, through the throttle) refreshes it, and `GET /auth/me` reports the session. Both are authenticated routes
- Connection rule (ADR 0002): the session lookup borrows, uses and returns its own short connection before the handler runs; no request nests a second session; `pool_timeout_s` is set explicitly
- Acceptance: a revoked or expired session is rejected on the next request; concurrent touches never error; the raw token and its hash appear in no log, event, error context or response beyond the one login response

## Milestone summary

**M3**
Outcome: Login and logout work over HTTP with opaque, database-backed sessions; business endpoints are still unprotected. Status: M3.0 done (ADR 0001 accepted); M3.1 done (issue #86, PR #87); M3.3 done (issue #88, PR #89); M3.4 done (issue #90, PR #91); M3.5 onward not started. Gate: not releasable; unprotected business routes remain until M4a. Re-scoped in v3.24: D1 settled as opaque, so the JWT module, refresh rotation and signing-key tickets are removed or rewritten.

## Cards

### WP M3-A: Decision and contracts

### M3.0 — Session-mechanism ADR (settles D1)

**Needs:** owner: you (approved 2026-10-30)

#### Spec

- **Scope:** ADR 0001 recording the opaque session mechanism, token and storage rules, lifetimes, revocation, the accepted costs and the revisit triggers. Key rotation is recorded as not applicable, with an emergency revoke-all procedure.
- **Excludes:** No code.
- **Needs:** owner: you (approved 2026-10-30)
- **Accept:**
  - [ ] Met: `docs/adr/0001-session-mechanism.md` exists with status Accepted and this plan marks D1 settled (D34).
  - [ ] Met: M3.1 to M3.8 re-scoped before starting, as the ticket required for an opaque outcome.

#### Outcome

Issue #82. PR #83 merged to `main` as merge commit `acbdba4` (branch `chore/82-token-key-rotation-adr`).

Evidence: Reviewed and approved ADR

---

### M3.1 — Session contracts and settings

**Needs:** M3.0 (done); ADR 0002 accepted by the owner

#### Spec

- **Scope:** Purpose: M3.3, M3.4 and M3.6 build against one frozen session contract. The token contracts were replaced by session contracts in `sessions/` (the folder was `tokens/`, renamed in this ticket): `ClientKind` (`api`, `cli`), `SessionRecord`, `ValidSession` (the record plus `AccessState`) and `SessionRepo` (create, `get_valid` with the kind required, touch, mark-reauthenticated, revoke, revoke-all-for-user, `purge_before`). The token hash port is now `SessionTokenHasher`. `AuthSettings` gained `session_api_idle_hours` (24), `session_api_absolute_days` (7), `session_cli_idle_days` (14), `session_cli_absolute_days` (30), `session_touch_interval_seconds` (300), `reauth_window_minutes` (30) and `trusted_proxies` (empty, entries validated as an IP address or CIDR network), and lost `signing_keys` and `active_kid` with their tests, README and CONTEXT rows and `.env` example lines. `PostgresSettings` gained `pool_timeout_s` (5.0), declared and not passed to the engine. The token fakes were replaced by `FakeSessionRepo` and `FakeSessionTokenHasher`. ADR 0002 status was updated to Accepted. The shape decisions are D36. Intermediate state (R3): nothing implements or reads any of it, so no session can be created yet.
- **Excludes:** No implementations, no startup wiring, no migration, no error codes, no routes.
- **Needs:** M3.0 (done); ADR 0002 accepted by the owner
- **Accept:**
  - [ ] Met in source, tests, fakes and env files: the token contracts and their fakes are gone. Not strictly "no reference": the final `git grep` still matches ADR 0001 (history) and, in `packages/config`, the removal note, the operator note and the tests that pin the removal. Those are deliberate.
  - [ ] Met: `Settings()` and `TestSettings()` build with no environment set, and leftover signing-key variables are ignored. The `unit and config` lane passed (114, run before the folder rename).
  - [ ] Met: defaults and floors of the new fields are tested, and `lint-imports` keeps all 7 contracts.
  - [ ] Met at unit level: `FakeSessionRepo` returns nothing for the other client kind in both directions and never returns a revoked, expired or inactive-user session, and touch never lowers an expiry. The `unit and authentication` lane passed (209, run after the rename; 27 fake tests and 15 contract tests).
  - [ ] Met: no new Alembic revision; `alembic heads` reports the single head `4794a1756a02`.
  - [ ] Met: CI passed 8 of 8, including the integration lanes and the Docker smoke job.
  - [ ] Not recorded here: a check that authentication imports nothing from `trutina.config` (no contract forbids it), and a wording check of the env examples and the docs beyond the removed-name grep.

#### Outcome

Issue #86. PR #87 merged to `main` as merge commit `8c53487` (6 commits, branch `feat/86-session-contracts-and-settings` deleted, 8 of 8 checks green). Verified locally before merge, as reported: ruff, `ty` and `lint-imports` (7 contracts kept) clean, lane coverage OK, `make pre-push` passing, 209 authentication unit tests after the rename, and 114 config and 180 storage unit tests before it. Premise checks: the ticket's claim that `trutina-authentication` lacked `trutina-shared` was wrong, since its `pyproject.toml` already declares it; the folder was renamed `sessions/`, reversing the ticket's recommendation to keep `tokens/`. Unblocks M3.3; the end-to-end criteria close in M3.8 (R4).

Evidence: G0, lanes authentication, config, infra postgres, CI QG1 to QG7

---

### M3.2 — Access-token module

#### Spec

- **Scope:** Removed by ADR 0001: there is no JWT. Token generation (256 bits from a CSPRNG) and hashing are small helpers inside M3.4. The number M3.2 held is not reused.

#### Outcome

---

### WP M3-B: Persistence and policy

### M3.3 — Session persistence

**Needs:** M3.1 (done); M4c.1 (not done, so the pool test builds its own one-connection pool)

#### Spec

- **Scope:** Purpose: M3.4 builds on a real store behind the frozen contract. `PostgresSessionRepo` and `SessionModel` live in `storage_postgres/session/`, over a `sessions` table (D37), migration `5bdeae152b29` on top of `4794a1756a02` with a tested downgrade. `get_valid` is one read-only query joining `users`, using the caller's `now` and strict expiry comparisons. Each write is one UPDATE or DELETE on its own short session, with `GREATEST` on touch and re-authentication. A rejected `create` raises `UNKNOWN_ERROR` with the violated constraint name and no cause. The adapter computes no lifetime and runs no purge of its own. `tools/purge-sessions.py` (`--older-than-days`, default 7, no setting) removes dead sessions by hand. `sessions` is in the `clean_pg_db` truncate list and `postgres_session_repo` is a fixture. ADR 0002 section 4 was amended, and the `SessionRepo.create` docstring now defines the duplicate-hash failure (docs only; the contract was frozen under R5). Intermediate state (R3): nothing calls the adapter, so no session can be created through the application yet.
- **Excludes:** No policy (lifetimes are computed by the service, as for throttling), no purge on session creation (moved to M3.4), no wiring of `pool_timeout_s`, no expiry-column indexes, no error code, no route, and no CLI-specific behavior.
- **Needs:** M3.1 (done); M4c.1 (not done, so the pool test builds its own one-connection pool)
- **Accept:**
  - [ ] Met at integration level: a revoked, idle-expired, absolutely-expired or deactivated-user session is not returned by `get_valid` on real PostgreSQL (integration lane green locally and in CI QG4).
  - [ ] Met: concurrent touches of one session never error and never move a time backward.
  - [ ] Met: revoke-all-for-user ends every session of that user and no other.
  - [ ] Met: a session of the other client kind is not returned by `get_valid`, in both directions.
  - [ ] Met: with a pool of one connection and no overflow every method completes, and more concurrent lookups than the pool size complete without a stall.
  - [ ] Met: `alembic heads` reported one head, `5bdeae152b29`, and `alembic check` reported no new operations. The round-trip test is in the integration lane, and CI QG4 and the Docker smoke job (QG7) passed.
  - [ ] Not recorded here: a manual run of `tools/purge-sessions.py` against seeded rows, a `git grep` audit of every `SessionRepo` implementer and caller, a local run of `tools/docker-smoke.sh`, and the manual negative checks.
  - [ ] Not recorded here: tests for a bad `client_kind` rejected by PostgreSQL, for a reactivated user's session becoming valid again, for revoking a mix of `api` and `cli` sessions, and for the one-statement lookup.
  - [ ] Not closed here, by design: a session actually created through the application, the service rules and the secret-safety criteria for session tokens. These close in M3.4 and M3.8 (R4).

#### Outcome

Issue #88. PR #89 merged to `main` as merge commit `62c7210` (6 commits: `0a13eb0`, `e2d1328`, `f2853ea`, `bcd5631`, `cdec686`, `5b54be8`; branch `feat/88-postgres-session-store` deleted, 8 of 8 checks green: QG1 to QG7). Verified locally before merge, as reported: `alembic upgrade head` ran, `alembic check` clean, 213 unit and 152 integration tests in the infra postgres lane, 209 authentication unit tests, `ruff format` (404 files already formatted), two further static checks reporting "All checks passed", `lint-imports` (7 contracts kept, 0 broken) and `make pre-push` passing. The commit those ran at is not recorded and they were not re-run at the merge commit. Premise checks: the card said the lifetime comes from the kind, a touch writes only when the interval has passed, and a bounded purge runs when a session is created. The contract puts the first two in the service, and its `create` takes no cutoff while `purge_before` has no batch limit, so the purge on creation moves to M3.4. Unblocks M3.4; the end-to-end criteria close in M3.8 (R4).

Evidence: G0, G-DOCKER (CI QG7), lanes infra postgres and authentication, `alembic check`, CI QG1 to QG7

---

### M3.4 — Session service

**Needs:** M3.3 (done), M2.8 (done)

#### Spec

- **Scope:** Purpose: M3.6 and M3.7 build on one working session service over the frozen `SessionRepo`. `SessionService`, `IssuedSession` and `SessionLifetime` live in `sessions/service.py`, and `Sha256SessionTokenHasher` (hex SHA-256 of the UTF-8 token, no salt, no pepper) in `sessions/sha256_hasher.py`, all exported from the package root. The service takes plain keyword-only values, not `AuthSettings`: the session and user repos, an `Authenticator` (the composition root passes `ThrottledAuthenticator`), a token hasher, a `Clock`, a lifetime per `ClientKind`, `touch_interval`, `reauth_window`, `purge_retention`, an optional event sink and an optional token factory (default 256 bits from a CSPRNG). `login` authenticates first, then makes one unbounded `purge_before` call with a cutoff of now minus the retention window, before the insert, and stores a session whose idle expiry is `min(now + idle, absolute)`; the raw token is returned once, in `IssuedSession`. `validate` rejects a blank or over-128-character token without hashing, looks the token up with its client kind, records a use only when the touch interval has passed, and raises one `AUTH_TOKEN_INVALID` with an empty context for every failure. `require_recent_auth` raises `AUTH_REAUTH_REQUIRED` once `authenticated_at` is a full window old (the window is exclusive). `reauthenticate` takes its identity from the session, verifies the password through the authenticator, so through the throttle, then refreshes `authenticated_at` without rotating the token. `logout` is idempotent and bound to the client kind; `revoke_all_for_user` ends both kinds. Three secret-free events (`auth.session_created`, `auth.session_revoked`, `auth.session_reauthenticated`) carry `subject_id` and `client_kind` only. `AUTH_TOKEN_INVALID` (401) and `AUTH_REAUTH_REQUIRED` (403) were added to the shared `ErrorCode` with API catalog entries, CLI `ERRORS` and `HINTS` entries and parity tests, in the same PR (the D19 pattern). Shape decisions are D38. Intermediate state (R3): nothing calls the service, so no session can be created through an app yet, and both new codes have a raiser but no route to carry them.
- **Excludes:** No HTTP, no rotation, no grace window, no `AUTH_REFRESH_CONFLICT`, no migration, no change to the frozen `SessionRepo` or `LoginAttemptRepo`, no `AuthSettings` field, no composition root, and no wiring of `pool_timeout_s`.
- **Needs:** M3.3 (done), M2.8 (done)
- **Accept:**
  - [ ] Met: an invalid, expired, revoked or malformed token raises one indistinguishable `AUTH_TOKEN_INVALID` with an empty context. The unit tests compare code, context and repr across a blank, unknown, oversized, other-kind, revoked, expired and disabled-user token, and the integration lifecycle test checks the same on PostgreSQL.
  - [ ] Met for the raw token: it appears in no event, log or error context. The unit leak test covers events, errors and log records. The integration sweep covers a log collector (with a control record), errors, events, and the `users`, `login_attempts`, `audit_events` and `sessions` tables. Not closed here: the stored hash made by the real hasher is not asserted absent from logs, events and error contexts (the unit test uses a fake whose hash embeds the token, and the `sessions` table holds the hash by design).
  - [ ] Met: a disabled user's session fails validation immediately (unit, and integration against the real `users` join).
  - [ ] Met at unit level: two logins give two different tokens, and logout of one leaves the other valid. Not recorded here at integration level.
  - [ ] Met: a session older than the window gets `AUTH_REAUTH_REQUIRED`, with an exclusive boundary; re-authentication refreshes `authenticated_at` without rotating the token (the integration test finds one row with the same hash); a wrong password or a throttled attempt leaves the session valid and unchanged. Met in unit tests, and in integration tests for the refresh and the wrong password.
  - [ ] Met: touch timing (no write inside the interval, a write exactly at it, idle expiry capped at the absolute expiry), strict client kinds in both directions, idempotent logout, revoke-all of both kinds, and the purge on login (cutoff, order before the insert, a failed purge creating no session).
  - [ ] Met: with a pool of one connection and no overflow, the whole flow (login, eight concurrent validations with a due touch, re-authentication, logout) completes on real PostgreSQL.
  - [ ] Met: `lint-imports` keeps all 7 contracts. No new Alembic revision.
  - [ ] Not closed here, by design: routes, the request-level connection rule, `Retry-After` and the credential criteria on real routes. These close in M3.6 to M3.8 (R4).
  - [ ] Not recorded here: per-test output of the five manual negative checks. The owner reported that all five failed as expected: a create-before-purge order in login, `>=` changed to `>` in `require_recent_auth`, `<` changed to `<=` in the touch check, a `field` key added to the `AUTH_TOKEN_INVALID` context, and `service.py` importing `trutina.core`. None of them removes a catalog entry.
  - [ ] Not recorded here: tests for `repr` and `str` of the validation result, for logout of an expired but unrevoked token, and for the default token factory (length and entropy); a local run of the whole `infra postgres` lane after the final commit; a local `tools/docker-smoke.sh` run (CI's QG7 passed); and which edits commit `bc081dd` made beyond its subject.

#### Outcome

Issue #90. PR #91 merged to `main` as merge commit `710539a` (5 commits: `f131e95`, `7c85b0d`, `776d8de`, `d4a0a02`, `bc081dd`; branch `feat/90-session-service` deleted, 8 of 8 checks green: QG1 to QG7). Verified locally before merge, as reported by the owner earlier in this work (run before the last commits, and not re-run at the merge commit): `ruff format` (409 files already formatted), `ruff check` and `ty` reporting "All checks passed", `lint-imports` (7 contracts kept, 0 broken), `make pre-push` passing with lane coverage OK (2012 collected), the unit lanes authentication 264, shared 115, api 268 and cli 432 passed, and the `infra postgres` lane 152 passed. That 152 equals the count recorded for M3.3, so it does not by itself show that the new file ran; that file alone ran 13 passed, and CI's QG4 passed. Premise checks: the card said the purge on creation would be bounded and that a limit would be decided here, but the frozen `purge_before` has no limit and unfreezing the contract was out of scope, so the purge is one unbounded call made before the insert (D38); ADR 0002 section 5 was amended to match (per the diff stat). The card said the login runs only after `ThrottledAuthenticator` succeeds; the service takes any `Authenticator` and relies on the composition root to pass the throttled one. The revoke-all event kind `"all"` was chosen during implementation and is not in ADR 0002's list. Unblocks M3.6 together with M3.5; the end-to-end criteria close in M3.8 (R4).

Evidence: G0, lanes authentication, shared, api, cli, infra postgres integration, CI QG1 to QG7

---

### M3.5 — Access state from session validation

**Needs:** M3.3 (done); M3.4 is done, so it can start now

#### Spec

- **Scope:** Decide whether `UserStatusChecker` survives as a thin wrapper over the validation join or is removed, and whether `AUTH_USER_DISABLED` is kept for writes or folded into `AUTH_TOKEN_INVALID`. Implement the outcome with catalogs and parity if a code remains.
- **Excludes:** No route wiring.
- **Needs:** M3.3 (done); M3.4 is done, so it can start now
- **Accept:**
  - [ ] The decision is recorded in this plan.
  - [ ] Disabled and missing users both report inactive, and parity tests pass.

#### Outcome

Evidence: G0, lanes authentication, infra postgres, api, cli

---

### WP M3-C: API integration

### M3.6 — API composition for sessions

**Needs:** M3.4 (done), M3.5

#### Spec

- **Scope:** `Container` gains the session service (stays frozen); providers; trusted-proxy client-IP resolver; `WWW-Authenticate` on 401. There is no signing-key startup check (D6 is moot). Compose and smoke script set the environment so the Docker smoke job keeps passing. Pool sizing is revisited with M4c.1's numbers. The auth dependency borrows, uses and returns its connection before the handler runs (ADR 0002, D35). No Origin middleware: cookies are deferred to ADR 0003.
- **Excludes:** No routes, no endpoint protection.
- **Needs:** M3.4 (done), M3.5
- **Accept:**
  - [ ] `X-Forwarded-For` is honored only from configured proxies, ignored otherwise.
  - [ ] The API starts without any signing configuration.
  - [ ] A test holding the pool at its limit shows the auth dependency does not keep a connection through the handler.
  - [ ] Docker smoke passes.

#### Outcome

Evidence: G0, G-DOCKER

---

### M3.7 — Auth routes

**Needs:** M3.6, M2.7, M2.1

#### Spec

- **Scope:** Public `POST /auth/login` and `/auth/logout`, and authenticated `POST /auth/reauth` (password only) and `GET /auth/me`, via Router, Mapper, Handler, Presenter; 429 with `Retry-After`; credential handling re-verified on real routes. Login takes the client kind from the route (`api`).
- **Excludes:** No refresh route, no protection of other endpoints.
- **Needs:** M3.6, M2.7, M2.1
- **Accept:**
  - [ ] A rejected password never appears in a response or log on the real route.
  - [ ] 401 responses carry `WWW-Authenticate`; throttle returns 429 with `Retry-After`.
  - [ ] Routes appear on the explicit public allowlist (2 auth).
  - [ ] `/auth/reauth` and `/auth/me` are not on the public allowlist and answer 401 without a valid session; re-authentication failures return 401 or 429 and leave the session valid.

#### Outcome

Evidence: G0, lanes api (unit and integration)

---

### M3.8 — Integration verification

**Needs:** M3.7

#### Spec

- **Scope:** Real-PostgreSQL end-to-end login, logout, revoked-session rejection, disabled user and concurrent touches over HTTP; docs; ADR cross-references; the structlog redaction pipeline with a real credential and session token flow.
- **Excludes:** No new behavior.
- **Needs:** M3.7
- **Accept:**
  - [ ] All M3 security criteria are covered by at least one integration test.
  - [ ] Migrations apply from an empty database.

#### Outcome

Evidence: G0, G-DOCKER
