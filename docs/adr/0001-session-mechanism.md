# ADR 0001: One opaque, database-backed session mechanism

- **Status:** Proposed (becomes Accepted on owner sign-off)
- **Date:** 2026-10-30
- **Deciders:** project owner
- **Settles:** D1 in the identity and authentication plan (v3.23)
- **Supersedes:** P8 (token lifetime and key rotation) and the JWT-specific parts of M3

## Context

- Core sees only an opaque `actor: str`. Identity never enters `trutina-core`.
- The API already reads the database on every write to check `is_active` (decision 5).
- The CLI needs opaque, database-backed sessions regardless of what the API uses (P5).
- Trutina is single-tenant. One API process type would verify tokens, and no second service does or is planned.
- `trutina-config` has no secrets-manager integration, so signing keys would come from environment variables.
- The data is financial. How fast a revocation takes effect matters.
- No token implementation exists. The token and refresh-token contracts are provisional and no app uses them.

## Options considered

|                             | A. JWT access token plus opaque refresh token                                      | B. One opaque session token                             |
| --------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Verification                | Signature check, no DB on reads                                                    | One indexed DB lookup per request                       |
| Revocation                  | Reads: up to 15 minutes. Writes: immediate                                         | Immediate for reads and writes                          |
| Secrets to manage           | Signing keys, `kid`, dual-key rotation, pinned algorithm                           | None. Tokens are random and stored as SHA-256 hashes    |
| Mechanisms to build         | JWT module, refresh rotation, family reuse detection, a separate CLI session table | One session table, shared by API and CLI                |
| Theft detection             | Refresh reuse detection                                                            | None. Bounded by lifetimes and revocation               |
| Scales to a second verifier | Yes, with asymmetric keys                                                          | No, it would need the database or an introspection call |

## Decision

Option B. API and CLI use the same session mechanism.

1. **Token.** 256 bits from a CSPRNG, presented to the API as `Authorization: Bearer <token>`. No cookies, because no browser client exists.
2. **Storage.** Only the SHA-256 hash is stored, through the existing deterministic-hash port (P4). It is never the password hasher. The raw token is returned once at login and never logged.
3. **Validation.** One query on every authenticated request: look up the session by hash, join the user, and require not revoked, idle expiry in the future, absolute expiry in the future, and `is_active`. The join also supplies `AccessState`, so M5 roles extend the same query. Times come from `Clock`, not SQL `now()`.
4. **Lifetimes (carried over from P8).** 14 days idle, 30 days absolute from session creation. Both are `AuthSettings` fields. `last_used_at` is refreshed at most once per touch interval (default 5 minutes), so reads do not each cause a write.
5. **No rotation.** A session token is not rotated per request. A new token is issued at each login only, so there is no session fixation.
6. **Revocation.** Logout revokes that session. A password change or deactivation revokes all of the user's sessions. A deactivated user also fails validation immediately through the join.
7. **Login.** A session is created only after `ThrottledAuthenticator` succeeds. Auth routes are `POST /auth/login` and `POST /auth/logout`. There is no refresh route.
8. **CLI.** Same table and same service, with a client-kind column. The CLI stores the token in a 0600 file or `TRUTINA_AUTH_TOKEN` (M4.5). CLI auth stays attribution-only (decision 9).
9. **Key rotation: not applicable.** There is no signing key. Emergency procedure: revoke every session with a single UPDATE, and users log in again. It is documented in the runbook at M5.7.

## Consequences

### Gained

- Revocation takes effect on the next request. The 15-minute read-exposure window in P8 is gone.
- No signing keys to generate, validate, rotate or leak, and no rolling-deploy key choreography.
- One mechanism for API and CLI. M4.5.1 shrinks to the CLI-specific parts.

### Accepted costs

- Every authenticated request needs a DB connection. The pool must be tuned (M4c.2). The default `pool_size` of 1 is not enough for this.
- There is no automatic theft detection. A stolen token works until it is revoked or expires (at most 14 days idle or 30 days absolute).
- Session lookup latency becomes part of every request. It is measured in M4c.2 against the provisional target of p95 under 20 ms.

### Superseded

- P8: 15-minute TTL, HS256, `kid`, dual-key verify, leeway, key-rotation procedure.
- The JWT-specific parts of M3. `TokenIssuer`, `TokenVerifier`, `AccessToken`, `RefreshTokenRepo` and the rotation types are replaced by session contracts in M3.1.
- The residual-risk table under "Token lifetime and key rotation" and the "reads stateless" half of decision 5. The "check the database on every write" half still holds, through the same lookup.
- `AUTH_REFRESH_CONFLICT` is dropped. `AUTH_USER_DISABLED` is folded into session validation unless M3.1 finds a reason to keep it.
- `AuthSettings.signing_keys` and `active_kid` are removed (cleanup ticket in M3.1).

### Unchanged

- Locked decisions 1 to 13, P1 to P7, D2 to D33. Core still sees only `actor: str`. The deploy gate (P1) still applies.

## Revisit triggers

Reopen this ADR if any of these happens:

- A second service must verify tokens without database access.
- Measured session-lookup p95 exceeds the M4c.2 target after pool tuning.
- A browser or third-party client needs delegated, self-contained tokens.

If it is reopened, the likely target is short-lived signed access tokens over these same sessions, so the session table stays the revocation source of truth.
