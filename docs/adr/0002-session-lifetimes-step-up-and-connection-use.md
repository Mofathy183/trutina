# ADR 0002: Per-client session lifetimes, step-up re-authentication and connection discipline

- **Status:** Accepted
- **Date:** 2026-11-04
- **Deciders:** project owner
- **Amends:** ADR 0001 (decisions 3, 4, 7 and 8). Recorded in the identity and authentication plan as D35 (v3.25)
- **Defers to:** ADR 0003 (browser transport: cookies, Origin check, CORS, CSP), written only when a web client is scheduled

## Context

- ADR 0001 chose one opaque, database-backed session mechanism with one lifetime pair (14 days idle, 30 days absolute) for API and CLI.
- The two clients differ. The CLI is an operator tool: it already holds the database URI, so its session guards attribution only (plan decision 9). API clients are remote and reach the data over the network.
- The data is financial. Posting is the commit point: postings are frozen and a journal entry can be posted once. Account deletion is destructive.
- ADR 0001 accepted that a stolen session token cannot be detected automatically. Something must limit what such a token can do.
- Every authenticated request now reads the database, and the default `pool_size` is 1 (`max_overflow` 10). How long a request holds a connection decides whether the pool stalls.
- No web client exists or is scheduled. Bearer transport (ADR 0001, decision 1) stays.

## Decision

### 1. Client kinds are strict

`client_kind` takes exactly two values, `api` and `cli`, enforced by a CHECK constraint. A session is valid only for the kind it was issued for: `get_valid(token_hash, client_kind)` takes the kind as a required argument, so no caller can omit it. A token of the wrong kind fails with the same indistinguishable `AUTH_TOKEN_INVALID` as any other bad token. The API validates `api` sessions only; the CLI validates `cli` sessions only. Each direction has a test.

### 2. Lifetimes are per kind and are settings

| Kind  | Idle     | Absolute |
| ----- | -------- | -------- |
| `api` | 24 hours | 7 days   |
| `cli` | 14 days  | 30 days  |

- Rule: on creation and on each touch, `idle_expires_at = min(now + idle, absolute_expires_at)`. The absolute limit is fixed at creation.
- `last_used_at` and the idle expiry are touched at most once per touch interval (default 300 seconds), so idle expiry is accurate only to that interval.
- All values are `AuthSettings` fields (`session_api_idle_hours`, `session_api_absolute_days`, `session_cli_idle_days`, `session_cli_absolute_days`, `session_touch_interval_seconds`), validated for shape only (each at least 1). An idle value above the absolute value is harmless because of the `min` rule.
- The numbers are provisional defaults. M4c.2 may revise them and freezes them (R5).

### 3. Step-up re-authentication on irreversible actions

- A session carries `authenticated_at`, set at login and again at each successful re-authentication. A fixed window, `AuthSettings.reauth_window_minutes` (default 30), counts from it. Ordinary use does not extend it.
- Step-up applies to the `api` kind at: `POST /postings/{journal_number}`, `DELETE /accounts/{code}`, and later user and role management (M5). It does not apply to reads, journal entry creation (a draft), or account creation.
- The session service exposes `require_recent_auth`. The API route dependency calls it before the handler runs, so a failure performs no write.
- Failure raises `AUTH_REAUTH_REQUIRED` (`auth.reauth_required`), HTTP 403, empty context. It is distinct from the 401 for an invalid or expired session, so a client can prompt for the password instead of logging the user out. It is the first 403 code; the permission 403 arrives with M5. Clients must key on `error_code`, not on status alone. API and CLI catalog entries and the parity tests land with it. The CLI never raises it.
- `POST /auth/reauth` takes a password only. The identity comes from the session, never from the body. The check goes through `ThrottledAuthenticator`, so the route cannot be used to guess passwords. Success updates `authenticated_at` and does not rotate the token. A wrong password returns `AUTH_INVALID_CREDENTIALS` (401) and a throttled attempt returns `AUTH_THROTTLED` (429); in both the session stays valid.
- The token is not rotated at re-authentication. Tokens are generated only by the server at login, so there is no fixation vector, and ADR 0001 decision 5 (no rotation) holds.
- The CLI has no step-up. It is an operator tool that holds the database URI, so a password prompt there guards nothing, and its audit rows stay untrusted. Documentation must say so.
- Threat model: step-up limits a stolen or leaked `api` token and an unattended client. A holder of the token can read data and create drafts but cannot post or delete without the password. It does not defend against a holder of database credentials.

### 4. Borrow, use, return: no connection held across a request

- The session lookup opens its own short session, runs the validation query and returns the connection before the handler starts. When a touch is due, the `UPDATE` runs in the same short session, with `GREATEST` on expiry so concurrent touches never move expiry backward. Otherwise the lookup is a read.
- No request holds one connection while asking for another. No connection is held while hashing: re-authentication loads the user, releases the connection, verifies the password, then borrows again to write `authenticated_at`.
- `PostgresSettings` gains `pool_timeout_s`, set explicitly (a few seconds), so exhaustion fails fast as `STORAGE_TIMEOUT` and does not hang for the library default. Pool size comes from M4c.1. The check is processes × (`pool_size` + `max_overflow`) against PostgreSQL `max_connections`.
- Proof: a load test fires more concurrent authenticated requests than the pool size and shows no stall (M4c.2). The cost of `pool_pre_ping` is measured there.

### 5. Session purge

A session is dead when revoked, idle-expired or absolute-expired. Dead rows older than 7 days are deleted by `tools/purge-sessions.py` (run by hand, as for login attempts) and by a bounded opportunistic batch when a session is created. Indexes on `token_hash` (unique), `user_id` and the expiry columns are decided in M3.3. Revoked rows are kept for the retention period for forensics, and the secret-free events below carry the audit trail.

### 6. Events, revocation and deferrals

- Secret-free events, each with `subject_id` and `client_kind` only, never a token, hash or IP: `auth.session_created`, `auth.session_revoked`, `auth.session_reauthenticated`.
- Logout revokes that session. Deactivation revokes all of a user's sessions. Revoking all other sessions on a password change waits for a password-change route, which does not exist (reset is deferred). The rehash after login never revokes anything.
- Deferred: session metadata (user agent, IP), because it is personal data with no reader today; cookie transport, Origin check, CORS, CSP and the cookie redaction markers (ADR 0003); an API-client CLI for regular users (M5), which would use the same Bearer sessions with the `api` kind.
- Gate: no web client ships before ADR 0003.

## Options considered

| Question | Options | Chosen |
| -------- | ------- | ------ |
| Lifetimes | One pair for both clients (ADR 0001); a pair per kind | Per kind: a remote client should not carry an operator-length session |
| Kind check | API accepts any kind; each side accepts its own only | Own only: a leaked 30-day operator token must not work through the network API |
| Step-up | None; at posting and delete; at every write | Posting and delete: the commit point and the destructive action, without prompting for drafts |
| Transport | Bearer; cookie | Bearer: no web client exists, and cookies add CSRF surface for no consumer |
| Connections | Hold one for the whole request; borrow and return | Borrow and return: nesting two connections per request deadlocks a small pool |

## Consequences

### Gained

- A leaked `api` token is bounded to 24 hours idle and 7 days absolute, and cannot post or delete without the password.
- An operator token cannot be replayed through the network API.
- Pool exhaustion fails fast and cannot deadlock on nested sessions.
- A browser client can be added later without changing the schema.

### Accepted costs

- One extra column (`authenticated_at`) and one extra route family (`/auth/reauth`, `/auth/me`).
- Re-authentication uses the hasher's slots (about 260 ms each, 4 at once). Throttling protects them.
- Real users re-enter the password about once per window when posting in a long session.
- A thief can still read data and create draft entries until the token is revoked or expires, and a draft created that way must be reviewed before it is posted.
- `idle_expires_at` is accurate only to the touch interval.
- A wrong password on `/auth/reauth` is a 401 that does not end the session, so clients must key on `error_code`.

### Open at the time of writing

- Whether account update (which can change the category and so the normal-balance side) needs step-up. Decide in M4a.2, or in the M5.0 permission matrix.
- The token hasher port was renamed `SessionTokenHasher` in M3.1.

### Superseded in ADR 0001

- Decision 3: the validation query also filters by `client_kind` and the session carries `authenticated_at`.
- Decision 4: the single lifetime pair.
- Decision 7: adds `POST /auth/reauth` and `GET /auth/me`, both authenticated. The public routes stay `POST /auth/login` and `POST /auth/logout`.
- Decision 8: the client-kind values and the CLI lifetimes.

### Unchanged

Bearer transport, SHA-256 hash storage, no rotation, revocation on logout and deactivation, and everything in the plan not listed here.

## Impact on planned tickets

| Ticket | Effect |
| ------ | ------ |
| M3.1 | Per-kind lifetime fields, `reauth_window_minutes`, touch interval, `trusted_proxies`; `PostgresSettings.pool_timeout_s`; contracts take `client_kind`, add mark-reauthenticated; token hasher naming decided |
| M3.3 | `client_kind` CHECK, `authenticated_at`, lifetime by kind, purge and indexes, every repo method on its own short session |
| M3.4 | `require_recent_auth`, re-authentication through the throttle, `AUTH_REAUTH_REQUIRED`, the three events |
| M3.6 | Connection discipline in the auth dependency; no Origin middleware |
| M3.7 | Login, logout, `POST /auth/reauth`, `GET /auth/me` |
| M4a.2 | Step-up dependency on posting and account delete; route inventory unchanged (2 system, 2 auth public) |
| M4.5.1 | `cli` kind, 14 and 30 day lifetimes, validated against the CLI only, no step-up |
| M4c.1, M4c.2 | Pool size and `pool_timeout_s`; re-auth load; concurrent-requests-above-pool test; `pool_pre_ping` cost |
| M5 | Step-up on user and role management; the API-client CLI uses `api` sessions |

## Revisit triggers

Reopen this ADR if any of these happens:

- A web client is scheduled (write ADR 0003 first).
- Measured lookup p95 exceeds the M4c.2 target after tuning the pool.
- Real users find the step-up window disruptive, or an incident shows a stolen token doing harm within the window.
- The CLI is given to anyone who should not hold database credentials.
