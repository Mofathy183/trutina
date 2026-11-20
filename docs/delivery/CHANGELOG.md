# Changelog

## Frozen status paragraph (v3.28)

How Trutina gets identity, authentication and later authorization without the accounting core knowing any of it exists. Status: v3.28 records M3.4 as done (issue #90, PR #91, merge commit `710539a`, 5 commits, 8 of 8 checks green, branch `feat/90-session-service` deleted): `SessionService` and `Sha256SessionTokenHasher` in `trutina-authentication`'s `sessions/` folder now implement login, validation, logout, revoke-all, step-up (`require_recent_auth`) and re-authentication over the frozen `SessionRepo`, and `AUTH_TOKEN_INVALID` and `AUTH_REAUTH_REQUIRED` are added to the shared errors and both app catalogs. It is service-only: no route, command or composition root calls it, and `PostgresSettings.pool_timeout_s` is still declared and not read. This is a status change that also records one decision (D38). Earlier, v3.27 records M3.3 as done (issue #88, PR #89, merge commit `62c7210`, 6 commits, 8 of 8 checks green, branch `feat/88-postgres-session-store` deleted): `PostgresSessionRepo` and `SessionModel` in `trutina-storage-postgres`'s `session/` folder now implement the frozen `SessionRepo` over a new `sessions` table (migration `5bdeae152b29`), with `tools/purge-sessions.py` for dead sessions. Nothing calls the adapter yet: no session service, route or composition root exists, and `PostgresSettings.pool_timeout_s` is still declared and not read. This is a status change that also records one decision (D37). Earlier, v3.26 records M3.1 as done (issue #86, PR #87, merge commit `8c53487`, 6 commits, 8 of 8 checks green, branch `feat/86-session-contracts-and-settings` deleted): the frozen, unimplemented session contracts (`SessionRepo`, `SessionRecord`, `ValidSession`, `ClientKind`, `SessionTokenHasher`) now live in `trutina-authentication`'s `sessions/` folder (renamed from `tokens/`) and replace the token contracts, and `AuthSettings` loses the signing-key fields and gains the session, re-authentication and trusted-proxy fields, with `PostgresSettings.pool_timeout_s` declared and not yet read. Nothing implements or reads any of it, and ADR 0002 is now Accepted. This is a status change that also records one decision (D36). Earlier, v3.25 records ADR 0002 (decision D35, no code changed): per-client session lifetimes, step-up re-authentication on posting and account delete, strict client kinds and a borrow-use-return rule for database connections; Bearer transport stays and cookies are deferred to ADR 0003 until a web client is scheduled. Earlier, v3.24 records D1 as settled by ADR 0001 (one opaque, database-backed session mechanism for API and CLI, decision D34) and re-scopes M3 accordingly (issue #82, PR #83, branch `chore/82-token-key-rotation-adr`; merge commit not recorded here yet); no code changed. Earlier, v3.23 records M2.8 as done and M2 as complete (issue #80, PR #81, merge commit `fe4928e`, 7 commits, 8 of 8 checks green, branch `test/80-credentials-integration-verification` deleted): integration tests in `trutina-storage-postgres` run the real registration, login and throttle services over real PostgreSQL and a real Argon2id hasher, and check that no password or stored hash reaches logs, error contexts, events or the `login_attempts` and `audit_events` tables. It adds no production code. It closes the M2 criteria at service level only: route-level criteria stay with M3.7 and M3.8. Earlier, v3.22 recorded M2.7 as done (issue #78, PR #79, merge commit `92a6982`, 12 commits, 8 of 8 checks green, branch `feat/78-login-throttling` deleted): `ThrottledAuthenticator` in `trutina-authentication` wraps any `Authenticator` and throttles failed logins per client IP and normalized email in a sliding window, before any lookup or hashing, raising `AUTH_THROTTLED` with `retry_after_seconds`. Known and unknown emails behave identically and no account is ever locked. It adds `AppError.throttled` and two `AuthSettings` fields. It is service-only: no route, command or app uses it yet. Earlier, v3.21 recorded M2.6 as done (issue #76, PR #77, merge commit `b0c1f9c`, 6 commits, 8 of 8 checks green, branch `feat/76-login-verification` deleted): `PasswordAuthenticator` in `trutina-authentication` verifies an email and a password. Unknown email, wrong password, disabled account, blank password and over-limit input all raise one indistinguishable `AUTH_INVALID_CREDENTIALS`, an unknown email verifies against a dummy hash made once with current parameters, and a stale hash is replaced after a successful login. It is service-only: no throttling, route, command or app uses it yet. Earlier, v3.20 recorded M2.5 as done (issue #74, PR #75, merge commit `7bce020`, 8 of 8 checks green, branch `feat/74-register-use-case` deleted): `RegistrationService` in `trutina-authentication` registers a user from an email and a password, with bounded and normalized input, a duplicate-email check before hashing, an Argon2id hash and one secret-free event. It is service-only: no route, command or app uses it yet. It also fixes the password and email input rules that login (M2.6) reuses, and adds `ErrorCode.INVALID_EMAIL`. Earlier, v3.19 recorded M2.4 as done (issue #72, PR #73, merge commit `5bb169e`, 8 of 8 checks green, branch `feat/72-login-attempt-storage` deleted): `LoginAttemptRepo` is frozen and has a PostgreSQL adapter, `PostgresLoginAttemptRepo`, over a `login_attempts` table, with a purge script in `tools/`. Nothing writes to it yet, so throttling is still to build on it. Earlier, v3.18 recorded M2.2 as done (issue #70, branch `feat/70-password-hasher`, CI green; its PR number and merge commit are not recorded here yet): `Argon2PasswordHasher` in `trutina-authentication`, Argon2id through `argon2-cffi`, with four `AuthSettings` cost and concurrency fields. Nothing uses it yet, so registration and login are still to build on it. M2.3 (v3.17; issue #68, PR #69, merge commit `919c131`), M2.1 (v3.16; issue #66, PR #67, merge commit `a348d50`), M2.0 (v3.15; issue #64, PR #65, merge commit `0ab8974`), M1c (v3.14), the MongoDB retirement (issue #60, PR #62, merge commit `f5f142e`; D14 superseded), M1a, M0a and M0b are complete. M1b (users) is done (issue #55, PR #56, merge commit `fb541c2`, all CI checks passed); its design decisions (D16 to D20) held as written. Shape decisions are locked; D1 (JWT versus one opaque session mechanism) is settled by ADR 0001 in favor of opaque sessions. The merged workspace has contracts, a concrete Argon2id password hasher, a service-only registration use case, a service-only login verification, a service-only login throttle, a PostgreSQL session store with a service-only session service on top (no route, command or composition root), configuration, and a required `actor` on journal, posting and account writes, validated by core; journal entries and postings persist it as `created_by`, and account writes record it in `audit_events`, all in PostgreSQL. Both apps still pass a fixed pre-auth constant until M4b.1 and M4.5.3. Next steps: M3.5, M4c.1 (pulled forward), deciding where `pool_timeout_s` is wired, and recording M2.2's PR number and merge commit and PR #83's merge commit. Nothing can be deployed to production before M5 (see Changes in v3.1).

## Version summaries

### v3.28 (2026-11-13)

is a status change that also records one decision. M3.4 is recorded as merged (issue #90, PR #91, merge commit `710539a`, 5 commits, 8 of 8 checks green, branch deleted). One decision (D38, the session service shape) is added; no earlier locked decision is edited, and D35's purge sentence is annotated as partly superseded. The M3.4 card is corrected where it did not match the frozen contract (the bounded purge on creation is one unbounded call). Two error codes landed (`AUTH_TOKEN_INVALID`, `AUTH_REAUTH_REQUIRED`) with API and CLI catalog entries. Nine known gaps are added, six are updated and one is closed. No migration was added (the diff stat shows none) and no security criterion changed.

### v3.27 (2026-11-09)

is a status change that also records one decision. M3.3 is recorded as merged (issue #88, PR #89, merge commit `62c7210`, 6 commits, 8 of 8 checks green, branch deleted). One decision (D37, the session store shape) is added; no earlier locked decision is edited. The M3.3 card is corrected where it did not match the frozen contract (lifetime, touch and purge-on-creation wording), and the bounded purge on session creation is recorded against M3.4. Seven known gaps are added, five are updated and one is closed (the wording gap around `touch`). One migration was added (`5bdeae152b29`). No security criterion changed.

### v3.26 (2026-11-07)

is a status change that also records one decision. M3.1 is recorded as merged (issue #86, PR #87, merge commit `8c53487`, 6 commits, 8 of 8 checks green, branch deleted). One decision (D36, the session contract and settings shape) is added; decisions 3 and 10, P4 and part of D10 are marked superseded and not rewritten. Six known gaps are added, one is closed (the pending removal of the signing-key settings and token contracts) and one is updated (merge style). No security criterion changed, and no migration was added.

### v3.25 (2026-11-04)

records ADR 0002 (`docs/adr/0002-session-lifetimes-step-up-and-connection-use.md`, Proposed until owner sign-off) as decision D35 and amends ADR 0001 (decisions 3, 4, 7 and 8). Sessions get strict client kinds (`api`, `cli`), lifetimes per kind (`api` 24 hours idle and 7 days absolute, `cli` 14 and 30 days, provisional until M4c.2), step-up re-authentication on posting and account delete with a new 403 code `AUTH_REAUTH_REQUIRED`, and a rule that no request holds a database connection across the handler. Bearer transport is unchanged and cookie transport is deferred to ADR 0003. M3.1, M3.3, M3.4, M3.6, M3.7, M4a.2, M4.5.1 and M4c.2 are re-scoped, and ADR 0001 is marked Accepted and partially superseded. The stale JWT-era lines in decision 5, the M5 list and the remaining items are corrected. No code changed, and no security criterion was weakened.

### v3.24 (2026-10-30)

settles D1. ADR 0001 (`docs/adr/0001-session-mechanism.md`, Accepted) chooses one opaque, database-backed session mechanism for both API and CLI, so there is no JWT, no signing key and no refresh rotation. M3 is re-scoped (M3.2 removed, M3.1, M3.3, M3.4 and M3.6 rewritten, no refresh route), P8 is superseded, M4c.1 is pulled forward, and one decision (D34) and six known gaps are added. No security criterion was weakened except the loss of automatic theft detection, recorded as an accepted cost. No code changed.

### v3.23 (2026-10-29)

is a status change: M2.8 is recorded as merged and M2 as complete. One decision (D33) and three known gaps are added, and four existing known-gap entries are updated. No earlier locked decision and no security criterion changed.

### v3.22 (2026-10-27)

is a status change: M2.7 is recorded as merged. Two decisions (D31, D32) and nine known-gap entries are added, several existing known-gap entries are updated, and the M2.4 email-cap constraint and the M2.3 retry-key question are closed. No earlier locked decision and no security criterion changed.

### v3.21 (2026-10-24)

is a status change: M2.6 is recorded as merged. One decision (D30) and five known gaps are added, and the three M2.6 constraints are marked met. No earlier locked decision and no security criterion changed.

### v3.20 (2026-10-24)

is a status change: M2.5 is recorded as merged, and M1b's issue, PR and merge commit are recorded. Two decisions (D28, D29) and five known gaps are added, D27's contract path is updated, and the open M2 items on password length, password normalization, email format and duplicate-email exposure are settled. No earlier locked decision other than that path changed, and no security criterion changed.

### v3.19 (2026-10-23)

is a status change: M2.4 is recorded as merged. One decision (D27) and five known gaps are added; no earlier locked decision and no security criterion changed.

### v3.18 (2026-10-22)

is a status change: M2.2 is recorded as merged. One decision (D26) and five known gaps are added, and the scope of M2.5 and M2.6 is extended; no earlier locked decision and no security criterion changed.

### v3.17 (2026-10-21)

is a status change: M2.3 is recorded as merged. One decision (D25) and four known gaps are added; no earlier locked decision and no security criterion changed.

### v3.16 (2026-10-21)

is a status change: M2.1 is recorded as merged. One decision (D24) and three known gaps are added; no earlier locked decision and no security criterion changed.

### v3.15 (2026-10-20)

is a status change: M2.0 is recorded as merged. One decision (D23) and four known gaps are added; no earlier locked decision and no security criterion changed.

### v3.14 (2026-10-19)

is a status change: M1c.2 is recorded as merged and M1c as complete. D21 (the audit table shape) and D22 (append-only by repository convention only) are added; no earlier locked decision and no security criterion changed.

### v3.13 (2026-10-18)

is a status change: M1c.1 is recorded as merged and the MongoDB adapter as deleted. Only D14 changes, from "Mongo frozen" to superseded; no other locked decision and no security criterion changed.

### v3.12 (2026-10-16)

is a planning change only: the remaining milestones are decomposed into work packages and atomic tickets (see the delivery plan), and no implementation status, locked decision or security criterion has changed.

## Change history

### Changes in v3.28

| Finding | Resolution |
|---|---|
| M3.4 finished | Issue #90; PR #91 merged to `main` as merge commit `710539a`, 8 of 8 checks green (QG1 to QG7), branch `feat/90-session-service` deleted (5 commits: `f131e95`, `7c85b0d`, `776d8de`, `d4a0a02`, `bc081dd`). Ticket card, M3 milestone, status paragraph, delivery status, merge order, three needs lines, packages and errors rows and file list updated |
| The session service shape needed decisions | D38 records them. D35's purge sentence is annotated as partly superseded, and ADR 0002 section 5 was amended in the PR (per the diff stat) |
| The M3.4 card did not match the frozen contract | "Bounded purge when a session is created" and "a limit is decided here" were corrected: `purge_before` has no batch limit and the contract was out of scope, so the purge is one unbounded call before the insert. The card's Scope was rewritten to what was built |
| Two error codes landed | `AUTH_TOKEN_INVALID` (`auth.token_invalid`, 401) and `AUTH_REAUTH_REQUIRED` (`auth.reauth_required`, 403), with API catalog entries, CLI `ERRORS` and `HINTS` entries and parity tests in the same PR. `AUTH_USER_DISABLED` was not added; M3.5 decides it |
| Known gaps | Nine added (unbounded purge cost, shared re-authentication throttle bucket, revoke-all event kind, `cli` exemption as a convention, service edge behaviors, the `credentials` import, tests not written, handler and boundary tests for the new codes, unrecorded verification); six updated (touch expiry re-check, expiry indexes, revoke on password change and deactivation, wiring, merge style, commit scopes); one closed (the missing automatic purge) |
| Merge style of PR #91 | Not confirmed whether it was squashed; added to the existing known gap |
| Commit subjects | Recorded in the existing scope gap: the scopes `shared`, `authentication` and `storage`, one subject with no scope, and one subject that names a file |
| Local verification | The results in the ticket card are those the owner reported earlier in this work, run before the last commits. The fields in the request for this update were left blank, so they were carried from that report, and they were not re-run at the merge commit. The version date 2026-11-13 is the working date, not read from the screenshot |
| Not recorded here | Per-test output of the five manual negative checks (the owner reported all five failed as expected), a local run of the whole `infra postgres` lane after the final commit, a local Docker smoke run, whether the PR was squashed, and what commit `bc081dd` changed beyond its subject. The ticket body was not attached, so the M3.4 card in v3.27 was used as the ticket |
| Not changed | No migration was added (the diff stat shows none). No security criterion changed. Decisions 1 to 13 (3, 5 and 10 annotated), P1 to P7 and D2 to D37 are untouched, except that D35's purge sentence is annotated as partly superseded |
| Open from v3.27 | M2.2's PR number and merge commit, and PR #83's merge commit, are still not recorded here; account update step-up; where `pool_timeout_s` is wired |

### Changes in v3.27

| Finding | Resolution |
|---|---|
| M3.3 finished | Issue #88; PR #89 merged to `main` as merge commit `62c7210`, 8 of 8 checks green (QG1 to QG7), branch `feat/88-postgres-session-store` deleted (6 commits). Ticket card, M3 milestone, status paragraph, delivery status, merge order, three needs lines, packages rows and file list updated |
| The session store shape needed decisions | D37 records them. ADR 0002 section 4 was amended in the PR, and the `SessionRepo.create` docstring now defines the duplicate-hash failure (docs only; the contract was frozen under R5) |
| The M3.3 card did not match the frozen contract | "Lifetime comes from the kind", "touch only when the interval has passed" and "a bounded purge when a session is created" were corrected. The adapter computes no lifetime, and the purge on creation moves to M3.4; one sentence was added to the M3.4 card to carry it |
| The card asked for the indexes purge needs | Only the owner index was created beside the unique hash. Expiry indexes wait for load data in M4c.2 (D37, known gap) |
| A duplicate hash or unknown user would have leaked a driver exception | `create` raises `UNKNOWN_ERROR` with the constraint name and no cause (D37) |
| `pool_timeout_s` | Not wired in M3.3. Where it is wired (before M3.6 or in M4c.2) is not decided here; known gap updated |
| Known gaps | Seven added (no automatic purge, purge script untested, touch does not re-check expiry, no expiry indexes, constraint name as the only diagnostic, four untested behaviors, unrecorded verification); five updated (purge script and Docker image, `pool_timeout_s`, duplicate hash, fake join, merge style); one closed (the `touch` wording) |
| Merge style of PR #89 | Not confirmed whether it was squashed; added to the existing known gap |
| Local verification | The results in the ticket card are those the owner reported earlier in this work, run on the working tree. The field in the request for this update was left blank, so they were carried from that report, and they were not re-run at the merge commit |
| Not recorded here | A manual run of `tools/purge-sessions.py`, the implementer and caller audit, a local Docker smoke, the manual negative checks, tests for four behaviors named in the card, and which edits the ADR 0002 change made beyond section 4 (its diff was larger than that amendment alone) |
| Not changed | One migration was added (`5bdeae152b29`). No security criterion, no `ErrorCode` and no other locked decision changed. Decisions 1 to 13 (3 and 10 annotated), P1 to P7 and D2 to D36 are untouched |
| Open from v3.26 | M2.2's PR number and merge commit, and PR #83's merge commit, are still not recorded here; account update step-up; where `pool_timeout_s` is wired |

### Changes in v3.26

| Finding | Resolution |
|---|---|
| M3.1 finished | Issue #86; PR #87 merged to `main` as merge commit `8c53487`, 8 of 8 checks green, branch `feat/86-session-contracts-and-settings` deleted (6 commits). Ticket card, M3 milestone, status paragraph, delivery status, merge order, M3.3 needs line, packages and config rows and file list updated |
| The session contract and settings shape needed decisions | D36 records them. ADR 0002 is Accepted, and its status line was updated in the PR |
| The `tokens/` folder now held sessions | Renamed `sessions/`, reversing the ticket's recommendation to keep `tokens/`; the token hash port is `SessionTokenHasher` (D36) |
| Locked decisions still written as live | Decisions 3 and 10, P4 and the token and rotation part of D10 are annotated as superseded or renamed; none is rewritten |
| The ticket said authentication lacked `trutina-shared` | Wrong: its `pyproject.toml` already declares it, so no dependency change was needed |
| Removed-name `git grep` cannot reach zero | Remaining matches are ADR 0001 history and the config removal note, operator note and pinning tests, all deliberate; recorded in the ticket card |
| Known gaps | Six added (separate touch and the M3.3 wording, unwired `pool_timeout_s`, no lifetime upper bound, duplicate hash and naive datetime, silent leftover signing-key variables, fake join); one closed (the pending signing-key and token removal); one updated (merge style) |
| Merge style of PR #87 | Not confirmed whether it was squashed; added to the existing known gap |
| Not recorded here | A check that authentication imports nothing from `trutina.config`, and a wording check of the env examples and docs beyond the removed-name grep |
| Not changed | No migration, no security criterion, no other locked decision. Decisions 1 to 13 (3 and 10 annotated), P1 to P7 and D2 to D35 are untouched |
| Open from v3.25 | M2.2's PR number and merge commit, and PR #83's merge commit, are still not recorded here; ADR 0002 section 4 wording; account update step-up |

### Changes in v3.25

| Finding | Resolution |
|---|---|
| ADR 0001 gave API and CLI one lifetime pair | ADR 0002 (D35): lifetimes per client kind, provisional defaults as settings, `api` 24 hours idle and 7 days absolute, `cli` 14 and 30 days |
| An operator token could be replayed through the API | Strict client kinds: each side validates its own kind only |
| No limit on what a stolen token can do | Step-up on posting and account delete with `AUTH_REAUTH_REQUIRED` (403); the CLI is exempt as an operator tool; threat model stated |
| A held connection per request could deadlock the pool | Borrow, use, return; explicit `pool_timeout_s`; a load test above the pool size in M4c.2 |
| Cookie transport proposed with no web client | Dropped for now; Bearer stays; cookies, Origin check, CORS and CSP move to ADR 0003, gated before any web client |
| "No 403 until M5" became false | `AUTH_REAUTH_REQUIRED` is the first 403; catalogs and parity tests land with M3.4 |
| Stale JWT-era lines | Decision 5, the M5 list, the P8 references and the remaining items corrected; ADR 0001 marked Accepted with an amendments section |
| Not changed | No code, no migration. Decisions 1 to 13 (decision 5 annotated), P1 to P7 and D2 to D34 are untouched |
| Open | Account update step-up; the token hasher naming (M3.1); M2.2's PR number and merge commit; PR #83's merge commit |

### Changes in v3.24

| Finding | Resolution |
|---|---|
| D1 was open and blocked M3 | Settled by ADR 0001: one opaque, database-backed session mechanism for API and CLI (D34). Approved by the owner on 2026-10-30 |
| The ticket was titled "Key-rotation ADR" | With no signing key there is nothing to rotate. The ADR records key rotation as not applicable and gives an emergency revoke-all procedure; the ticket is retitled |
| M3 was built around JWT and refresh rotation | Re-scoped: M3.2 removed, M3.1, M3.3, M3.4 and M3.6 rewritten, M3.7 has login and logout only, M3.8 unchanged in shape. `AUTH_REFRESH_CONFLICT` dropped, `AUTH_USER_DISABLED` decided in M3.5 |
| P8 and the token-lifetime section | Marked superseded and kept as history; the 14 and 30 day lifetimes carry over to sessions |
| D6 (key validation at startup) | Moot, because no signing key exists; the API starts without signing configuration |
| Every authenticated request now touches the database | M4c.1 (expected load) pulled forward to size the pool; recorded as a known gap and a revisit trigger |
| Knock-on edits | M4a.2 allowlist is 2 system and 2 auth routes; M4.5.1 reuses the sessions table and service; read routes loading the access state is settled as yes |
| Theft detection | Lost with refresh reuse detection; accepted and recorded, bounded by lifetimes and instant revoke |
| Not changed | No code, no migration. Decisions 1 to 13, P1 to P7 (except P8) and D2 to D33 are untouched |
| Open from v3.23 | M2.2's PR number and merge commit, and M3.0's merge commit (PR #83), are not recorded here |

### Changes in v3.23

| Finding | Resolution |
|---|---|
| M2.8 finished | Issue #80; PR #81 merged to `main` as merge commit `fe4928e`, 8 of 8 checks green, branch `test/80-credentials-integration-verification` deleted (7 commits). Ticket card, M2 milestone, status paragraph, delivery-plan status, decision, known gaps and file list updated. M2 is complete |
| Where the end-to-end test can live | Only `trutina-storage-postgres`, because of the layering and logging import contracts (D33) |
| A first-run failure | One test assumed a stale hash survives a login under a different hasher. The code was right and the test was fixed; the cause is recorded as a known gap |
| Criteria that cannot close at this layer | Route-level 422 bodies, `Retry-After` and the structlog pipeline with a real credential flow stay with M3.7 and M3.8, stated rather than claimed |
| Doc drift from M2.5 to M2.7 | Corrected in ARCHITECTURE, PROJECT_CONTEXT, authentication CONTEXT, the config README, `.env.test.example`, the root README, ROADMAP and AGENTS |
| Test count and the last commit | The last commit extended the registration tests; the final test count is not recorded here |
| Manual negative checks for M2.8 | Not recorded here as run |
| Merge style of PR #81 | Not confirmed whether it was squashed; added to the existing known gap |
| Open from v3.22 | M2.2's PR number and merge commit are still not recorded here |

### Changes in v3.22

| Finding | Resolution |
|---|---|
| M2.7 finished | Issue #78; PR #79 merged to `main` as merge commit `92a6982`, 8 of 8 checks green, branch `feat/78-login-throttling` deleted (12 commits). Ticket card, M2 milestone, status paragraph, packages rows, delivery-plan status, decisions, known gaps and file list updated |
| The ticket left the retry delay open | The window length, an upper bound, because `LoginAttemptRepo` is frozen and has no oldest-failure query (D31) |
| The ticket asked whether an `AppError` constructor owns the key | Yes: `AppError.throttled` (D32) |
| Where throttling lives | A decorator, `ThrottledAuthenticator`, so `PasswordAuthenticator`'s tested properties are unchanged and need no clock or settings (D31) |
| A throttled attempt could extend its own lockout | Throttled attempts are never recorded; pinned by a test |
| The M2.4 constraint on recording only capped emails | Met: an over-limit email is neither counted nor stored |
| "A success clears only that pair" had no throttle-level test | Added in the last commit of the PR |
| Stale wording that throttling was still to come | Corrected in the authentication, storage-postgres, ARCHITECTURE, AGENTS and PROJECT_CONTEXT docs and in the purge script comment, and in `PasswordAuthenticator` and `Authenticator` docstrings; a grep for the old wording is clean |
| Plan draft said "4 commits" | The branch had 12; recorded as 12 |
| Manual negative checks for M2.7 | Not recorded here as run |
| Merge style of PR #79 | Not confirmed whether it was squashed; added to the existing known gap |
| Open from v3.20 | M2.2's PR number and merge commit are still not recorded here |

### Changes in v3.21

| Finding | Resolution |
|---|---|
| M2.6 finished | Issue #76; PR #77 merged to `main` as merge commit `b0c1f9c`, 8 of 8 checks green, branch `feat/76-login-verification` deleted (6 commits). Ticket card, M2 milestone, status paragraph, packages and errors rows, delivery-plan status, known gaps and file list updated |
| The ticket said "`Authenticator` implementation" and "times from `Clock`" | `PasswordAuthenticator` implements the existing contract. Nothing in M2.6 uses time, so there is no `Clock` dependency; it arrives with throttling (D30) |
| The dummy hash had to use current parameters, but `hash()` is async | An async `create()` makes it once; the constructor takes it as an argument (D30) |
| Blank and over-limit input could be hashed | Rejected before any lookup or hash, with the same error as every other failure. The faster return is recorded as a known gap, not a leak |
| Whether a rehash write failure should fail the login | It propagates unchanged (D30); recorded as a known gap with the unconditional-write caveat |
| The three constraints on M2.6 from M2.3 and M2.5 | Empty error context, dummy hash from `hash()` at startup, and no registration-only rules at login are all met and marked in the known-gap list |
| Merge style and commit subjects of PR #77 | Not confirmed from the PR page whether it was squashed; two docs commits share one subject. Both added to the existing known gaps |
| Manual negative checks for M2.6 | Not recorded here as run |
| Open from v3.20 | M2.2's PR number and merge commit are still not recorded here |

### Changes in v3.20

| Finding | Resolution |
|---|---|
| M2.5 finished | Issue #74; PR #75 merged to `main` as merge commit `7bce020`, 8 of 8 checks green, branch `feat/74-register-use-case` deleted (11 commits). Ticket card, M2 milestone, status paragraph, packages and errors rows, delivery-plan status and file list updated |
| The ticket said passwords must not be trimmed | Revised before implementation: NFKC, then leading and trailing whitespace is stripped, in one function shared with login. A whitespace-only password is rejected as a missing one. Recorded in D28 |
| The ticket left the password limits, email rule and duplicate exposure open | Settled in D28 and D29: maximum 128 and minimum 8 characters, email shape at registration only with a 254 limit, and the duplicate error propagates at the service with public exposure left to M5.6 |
| No `ErrorCode` fit a malformed email | Added `INVALID_EMAIL` (`user.invalid_email`, 422) with API and CLI catalog entries and parity tests in the same PR (the D19 pattern) |
| A Pydantic validator would downgrade the new code to `UNKNOWN_ERROR` | The rules are checked in the service and violations are built directly, so the real code stays on `violation.code` (D29) |
| The credentials folder was becoming a flat pile of files | Grouped into `passwords/`, `users/` and `login/` with no behavior change. D27's contract path is now `credentials/login/attempts.py` |
| Authentication needed `AppError` and `ValidationAppError` | `trutina-authentication` now depends on `trutina-shared`; `uv.lock` regenerated and the dependency tables updated |
| M1b had no recorded issue, PR or merge commit | Recorded: issue #55, PR #56, merge commit `fb541c2`, all CI checks passed. M1b's cards updated from "PR pending" to done |
| Merge style and commit scopes of PR #75 | Not confirmed from the PR page whether it was squashed; commit scopes were mixed (`auth` and `authentication`). Both recorded as known gaps |
| M2.2's PR number and merge commit | Still not recorded here |
| Manual import-linter negative check for M2.5 | Not recorded here as run |

### Changes in v3.19

| Finding | Resolution |
|---|---|
| M2.4 finished | Issue #72 closed; PR #73 merged to `main` as merge commit `5bb169e`, 8 of 8 checks green, branch `feat/72-login-attempt-storage` deleted (14 commits). Ticket card, M2 milestone, status paragraph, packages row, delivery-plan status, known gaps and file list updated |
| R5 asked for the provisional `LoginAttemptRepo` to be frozen by the ticket that names it | Frozen in M2.4: IP matched as given, email matched through `normalize_email()`, aware UTC times, no domain errors. D27 records the table and the semantics |
| Where the adapter lives | A new `storage_postgres/login_attempt/` folder, not `identity/`: one folder per persisted authentication concern, and `identity/` stays users-only. The contract stays in `credentials/attempts.py` |
| The fake matched emails with `casefold()` only | Now uses `normalize_email()`, so fake and adapter agree on whitespace, with a test |
| The repository must never log the IP or the email | Pinned by an integration test added in the last commit of the PR |
| No scheduler for retention | `tools/purge-login-attempts.py` added as the documented purge path, verified once by hand; the script is not in the Docker image, recorded with four other known gaps |
| Stale docs found | PROJECT_CONTEXT's identity bullet had a stray editing fragment mid-sentence; rewritten. Authentication CONTEXT's Direction line had a typo ("forUserRepo"); fixed |
| Merge style of PR #73 | Not confirmed from the PR page; the squash-only repository setting is still not confirmed |
| M1b, M2.2 status | Unchanged: issue, PR and merge commit still not recorded here for M1b, and PR number and merge commit not recorded for M2.2 |

### Changes in v3.18

| Finding | Resolution |
|---|---|
| M2.2 finished | Issue #70 closed; branch `feat/70-password-hasher` (12 commits) merged to `main` with CI green. The PR number and merge commit are not recorded here yet. Ticket card, M2 milestone, status paragraph, packages and config rows, D26, known gaps and file list updated |
| The ticket left the library open | Argon2id through `argon2-cffi` 25.1.0, verified on Python 3.14.4 on Windows and in the Docker builder (smoke run); D26 records the choice and the rejected options |
| The contract was silent on `needs_rehash` for a malformed hash | It returns `True`, documented on the class and pinned by a test; D26 |
| `.env.test.example` used unprefixed variables that `TestSettings` ignores | Corrected to `TRUTINA_TEST_` in the same PR. The ticket had put this out of scope as a separate fix; it was included because the new test-namespace entries needed the prefix. The logging `auto` comments were corrected too |
| Password length, normalization and the dummy hash had no owner | M2.5 scope now includes a maximum length and a normalization decision; M2.6 scope says the dummy hash is made at startup with `hash()`; both recorded as known gaps |
| Cost and memory figures | About 260 ms per hash (single run) and about 256 MiB peak per process at the defaults; recorded in D26 and in the authentication CONTEXT, and left to M4c.2 to measure under load |
| Merge style of the PR | Not recorded here. Squash-only is still not confirmed as a repository setting |
| M1b status | Unchanged: on `main`, issue, PR and merge commit still not recorded here |

### Changes in v3.17

| Finding | Resolution |
|---|---|
| M2.3 finished | Issue #68 closed; PR #69 merged to `main` as merge commit `919c131`, 8 of 8 checks green, branch `feat/68-auth-error-codes` deleted (7 commits). Ticket card, M2 milestone, status paragraph, errors row, delivery-plan status and file list updated |
| The ticket left the retry contract open | Decided as `context["retry_after_seconds"]`, a digits-only string, with the header omitted when the value is absent or invalid; D25 records it as the contract M2.7 must honor |
| The ticket's unverified source assumptions | Checked: `_response_headers` took only the code and gained a context argument; the catalog templates have no placeholders, so `_fill()` is not involved; `FIELD_LABELS` is read by `format_app_error()`, where a `field` context key overrides it |
| A single-field label would leak which credential was wrong | The CLI labels invalid credentials `credentials`, pinned by a test; the context-override hazard is recorded as a constraint on M2.6 |
| Cosmetic and verification limits | Recorded as known gaps: the "Validation Error" panel title, the missing throttle label, and handler-level-only `Retry-After` evidence |
| Merge style of PR #69 | Merge commit with its seven commits on `main`; added to the merge-style known gap. Squash-only is still not enforced |
| M1b status | Unchanged: on `main`, issue, PR and merge commit still not recorded here |

### Changes in v3.16

| Finding | Resolution |
|---|---|
| M2.1 finished | Issue #66 closed; PR #67 merged to `main` as merge commit `a348d50`, 8 of 8 checks green, branch `feat/66-secret-safe-validation-errors` deleted (9 commits). Ticket card, M2 milestone, status paragraph, delivery-plan status and file list updated |
| The ticket premise was partly wrong | The leak was in `FieldViolation.value`, which no presentation layer renders. The API and CLI needed regression tests, not code; recorded in the card |
| A `missing` error leaks a sibling credential | Pydantic reports the parent object as the input. Fixed by masking credential-keyed entries in container inputs; D24 records the rule |
| Marker list now exists in two packages | Recorded as a known gap, with the other two limits (`msg` text, sets and Click errors). Not fixed here |
| Merge style of PR #67 | Not recorded here. The squash-only repository setting is still not confirmed |
| M1b status | Unchanged: on `main`, issue, PR and merge commit still not recorded here |

### Changes in v3.15

| Finding | Resolution |
|---|---|
| M2.0 finished | Issue #64 closed; PR #65 merged to `main` as merge commit `0ab8974`, 8 of 8 checks green, branch deleted. Ticket card, M2 milestone, delivery-plan status and file list updated |
| The ticket premise was partly wrong | The substring markers already covered the four credential keys. The delivered change is nested redaction, not a longer marker list; recorded in the card |
| Nested credentials were logged in clear | Reproduced by the negative check: 10 new tests fail on the old `_redact_value`. Fixed by recursion; D23 records the rule |
| Free-text, hyphenated-key, cycle and monetary-recursion limits | Recorded as four known gaps, not fixed here |
| PR #65 used a merge commit | Added to the existing merge-style known gap. Squash-only is still not enforced |
| M1b status | Unchanged: on `main`, issue, PR and merge commit still not recorded here |

### Changes in v3.14

| Finding | Resolution |
|---|---|
| M1c.2 finished | Issue #58 closed; PR #63 merged to `main` as merge commit `b76dcd3`, 8 of 8 checks green, branch `feat/58-account-audit-events`. M1c is complete. Ticket card, M1c milestone, status and file list updated |
| Account writes were validated but not attributed in storage | Account create, update and delete now write an `audit_events` row in the same transaction. Migration `41065b2e2190` on top of `373da73ec0bb`. Account attribution is no longer a known gap; the fixed pre-auth constants remain until M4b.1 and M4.5.3 |
| The audit table shape needed a decision | D21: shape, CHECK, no foreign key, database-stamped time, one row per successful call, `UNKNOWN_ERROR` for a rejected audit insert |
| Append-only is not enforced by the database | D22 and a known gap: repository convention only; a trigger or restricted role is a separate, unscheduled ticket |
| The delete path had no `IntegrityError` handling | Found while planning the ticket: a failing audit insert would have leaked a raw `IntegrityError`. The delete path now translates it to `UNKNOWN_ERROR`, and a test proves the rollback |
| The `PostgresAccountRepo._on_duplicate` docstring named the wrong constraint prefix | Corrected in PR #63 (`uq_accounts_*`). The known gap is removed |
| Stale layout entry in AGENTS | The nonexistent `models.py` was removed from the storage-postgres layout and `audit/model.py` added |
| M1b status | Present on `main`: its users migration was already the head before M1c.2 and `identity/` is tracked. Issue, PR and merge commit are still not recorded here, and the M1b.1 ticket card keeps its earlier wording until they are |

### Changes in v3.13

| Finding | Resolution |
|---|---|
| M1c.1 finished | Issue #57 closed; PR #61 merged to `main` as merge commit `d433a5a`, CI green. Ticket card, M1c milestone and status updated; M1c.2 is unblocked |
| The MongoDB adapter was unused | Issue #60 closed; PR #62 merged as merge commit `f5f142e`, CI green, deleting the `trutina-storage-mongo` package. D14 is marked superseded. Mongo is removed from M1c.2's exclusions, from D5 and from the known gaps |
| M1c.1 scope narrowed while in flight | The Mongo account adapter change and its pinning tests were dropped by owner decision before the retirement; the ticket card now states what was delivered |
| PR #61 and PR #62 were merged with merge commits | The existing merge-style known gap now names them; squash-only is still not enforced |
| M1b status | Not reported in this update, so unchanged: implemented, merge not recorded |
| Older entries still name Mongo | Completed-milestone history, file lists and earlier change tables are kept as written because they record what was true then. The CLI storage-hint known gap that mentions MongoDB is left as written until it is checked against the current source |

### Changes in v3.12

| Finding | Resolution |
|---|---|
| Milestones were too large for one reviewable branch | Delivery plan added: work packages and tickets for M1b closeout, M1c, M2, M3, M4a to M4c, M4.5, M5, with scope, exclusions, dependencies, acceptance and evidence. No implementation is recorded as done |
| The authenticated test client was planned in M4b, after M4a protects the routes | Moved to M4a.1 so the suite stays green; no decision changed |
| The Docker smoke job runs in a production environment without keys | M3.6 and M4a.3 own the compose and smoke-script settings |
| Trusted-proxy handling had no home | Config in M3.1, resolver in M3.6, used by the login route in M3.7; M2.7 takes an opaque IP |
| Release gates were scattered | Gathered into the release gates section (G0, G-DOCKER, R1 to R5) |

### Changes in v3.11

| Finding | Resolution |
|---|---|
| M1b was final but unimplemented | Implemented on the feature branch; D16 to D20 held without change. PR pending, so no merge record yet |
| The "every code has both" test would fail on `REQUEST_VALIDATION_ERROR` | Excluded by name in each app's parity test, recorded as a known gap |
| CLI and API CONTEXT said a missing catalog entry is only a manual check | Updated: the parity tests now fail the build for it |
| Architecture and agent docs listed a flat authentication layout, and said no package depends on it | Corrected to the four-folder layout and to the one dependent, `trutina-storage-postgres` |
| `alembic check` was run without its config flag | Done: clean when run with the config flag |
| Docker smoke fails locally on Windows Git Bash at the migration step | Fixed locally with MSYS_NO_PATHCONV=1 and a free port 8000; the full run passes (build, four migrations, API health, structured logging). CI remains the authoritative check |

### Changes in v3.10

| Finding | Resolution |
|---|---|
| M1b had no final shape | Ticket finalized with decisions D16 to D20; status is final, not yet filed or implemented |
| A separate `email_key` column was proposed for case-insensitive email uniqueness | D16: dropped. A single email column is normalized on write by the `User` model, so a plain unique index is enough |
| `User.created_at` conflicted with the database-stamped timestamp mixin | D17: the database is authoritative; the passed value is ignored |
| Disabling a user had no operation, and a miss had no behavior | D18: `set_active` added; unknown users raise `UNKNOWN_USER` |
| A duplicate-email error could put personal data into logs and responses | D19: new codes with catalog entries, and no email value in the error context |
| Whether `password_hash` should be nullable for a future OAuth | D20: stays `NOT NULL`; OAuth identities get their own table later, recorded as a deferred item |
| Authentication Docker manifest and watch entries were deferred in M0a-C | They land with M1b, since the storage package now depends on authentication |
| Stale text found: the CLI storage hint mentions MongoDB, and an account repository docstring names the wrong index prefix | Recorded as known gaps, outside M1b scope |

### Changes in v3.9

| Finding | Resolution |
|---|---|
| M1a ticket 2 finished | Issue #52, PR #54 merged to `main` (merge commit `e9dd41b`, CI green), branch `feat/persist-created-by`. M1a is complete |
| Plan status said ticket 2 was "drafted, not yet filed" and that the actor was not persisted | Updated: the actor is persisted as `created_by` in PostgreSQL for journal entries and postings. Next is M1b or M1c |
| Keeping Mongo at `created_by` parity would maintain a backend no feature targets | D14: Mongo frozen. Its adapters accept the keyword and do not store it, pinned by a test per repository. D5 and M1c reworded |
| Storage shape of the attribution needed a decision | D15: required keyword-only `created_by` on the repo contracts, a nullable no-FK column on entries and postings only, off the domain schemas |
| Ticket 2 might not fit one PR, so the migration was to be split out if needed | Delivered as one PR. The commit history keeps the schema, contract change, tests and docs separate |
| Handler forwarding was deferred from ticket 1 because no fake could observe it | Done: fakes record `saved_created_by`, all four handlers are tested, and one end-to-end test reads the columns back with raw SQL |
| A model change shipped without its migration failed 23 integration tests with a misleading error | Fixed by adding the migration. Recorded as a known gap, with `alembic check` as a candidate CI step |
| `ty` missed callers of the changed contract again | Recorded as a known gap. The audit is a `git grep` plus the integration lanes |
| A CLI unit test passed locally by reaching a real PostgreSQL and failed in CI | Fixed in the PR by injecting the posting repository. Recorded as a known gap with a possible unit-lane guard |
| Merge style left red intermediate commits on main again | Recorded as a known gap, with a squash-only repository setting as the fix |

### Changes in v3.8

| Finding | Resolution |
|---|---|
| M1a ticket 1 finished | Issue #51, PR #53 merged to `main` (commit `555430e`, 9 of 9 checks green); 12 commits, feature branch deleted |
| Plan status said "implemented on a branch, not yet merged" | Updated: ticket 1 done; ticket 2 is next |
| Ticket 2 had no written shape | Drafted: keyword-only `created_by`, fake hook, forwarding tests through the four handlers, nullable column with a tested downgrade. Not yet filed |
| Merge style leaves red intermediate commits on main | Recorded as a known gap; prefer squash-merge for ticket 2 |

### Changes in v3.7

| Finding | Resolution |
|---|---|
| M1a handler format check placement | Deferred from M1a to M4b: today's only value is a trusted constant, so a validator guards nothing. D4 reworded |
| Where the blank-actor rule lives | `trutina-shared` (D12), not a new core module, because three write services will use it |
| One pre-auth constant for both apps | Split into `system:pre-auth:api` and `system:pre-auth:cli` (D13) so stored rows record which application wrote them |
| `ty` assumed to catch missed callers of the new required parameter | It does not for untyped fixtures or `app.state` (it passed with five callers missing). Gate is an AST audit (`audit_actor_calls.py`, not committed) plus the integration lanes |
| `BlockingPortal.call` keyword arguments | Confirmed it takes `(func, *args)` only (anyio 4.15.1); keyword-only `actor` goes through `functools.partial` |

### Changes in v3.6

| Finding | Resolution |
|---|---|
| M0b finished | Config: issue #48, PR #49. Package: issue #47, PR #50. Both merged to `main` with 9 of 9 checks green |
| Three planned PRs (A config, B package, C docs) | Delivered as two: docs folded into the package PR so the PR describes exactly what it merges |
| Flat module layout in the package | Regrouped into identity, credentials, tokens and shared folders; public imports unchanged |
| Circular import on first local test run (a cross-folder import from the package root) | D11: cross-folder imports use the sibling's submodule path |
| Four contracts are provisional | Unchanged: finalized at M1b (`UserRepo`), M2 (`LoginAttemptRepo`) and M3 (tokens, refresh repo) |
| Next unit is large | M1a is size-checked before its ticket is filed; split along layer boundaries if it does not fit one PR |

### Changes in v3.5

| Finding | Resolution |
|---|---|
| M0a finished; the plan still said "next step is M0a-C" | M0a recorded complete (A #44, B #42, C #46); duplicated M0a bullets removed |
| Env-var dict keys are lower-cased, plain strings are not | M0b-A: `AuthSettings` case-folds key ids and `active_kid`, with tests |
| CI has no `.env.test`, so the test namespace would silently be production | D9: workflows set `TRUTINA_TEST_ENVIRONMENT=test` |
| Contracts, fakes and linter contracts needed a shape | M0b-B drafted with D10; four contracts marked provisional until M3 and M2; contract checked on a stand-in tree |
| Stale "SyntaxError" docs item | Verified already closed; dropped from M0b |
| Docs must not describe unbuilt behavior | M0b-C drafted: every doc says contracts only, not consumed by any app |

### Changes in v3.4

| Finding | Resolution |
|---|---|
| M0a-A merged | PR #44 closes issue #41; all checks green on `main` |
| Observability pipeline merged | PR #40 closes issue #38; unblocks M0a-C |
| `trutina-cli trial-balance` opened the shell instead of running | M0a-B: `_known_commands` reads `registered_commands` too; recurrence-guard and `run()` tests; Known Gap closed |
| M0a-C scope overstated | Dockerfile and `compose.yml` Postgres already done; remaining work listed under M0a |
| Root docs still call compose MongoDB-only | To be corrected in M0a-C |

### Changes in v3.3

| Finding | Resolution |
|---|---|
| Marker derivation matched any path segment of the absolute path | D7: prefix table, `pytest_configure` registration check |
| Empty or mistyped selections passed silently (exit code 5) | D8: strict by default, `--allow-empty` opt-in |
| Tests could belong to no CI lane | D8: `tools/ci/check-lane-coverage.sh` in QG1 |
| No lane selected `authentication` tests | Added to the QG2 unit and integration selectors |
| Authentication contracts cannot name a missing module | Moved to M0b with the package (D1, option b) |

### Changes in v3.2

| Finding | Resolution |
|---|---|
| M1 locked refresh-token schema before D1 | Refresh-token tables moved to M3 |
| M1 too large | Split into M1a, M1b, M1c |
| Mongo audit parity unspecified | D5: Postgres-only audit |
| Actor validation versus core rule | D4: handlers validate format |
| Audit atomicity | M1c rollback acceptance test |
| Key validation could break Alembic and CLI | D6 and M0b test |

### Changes in v3.1

| Review finding | Resolution |
|---|---|
| No environment concept; P1 fail-open | D2, M0b setting, P1 reworded, smoke test and TestSettings covered |
| Passwords echoed by error layer | M2 rule and test |
| Refresh reuse false positives, `now()` versus Clock | M3 grace window, `least()` expiry, Clock times |
| Mongo contracts broken by M1 | M1 updates Mongo adapters |
| Audit cannot record deletes | D3, M1b `audit_events` |
| Disabled-user code versus "no 403" | New 401 and 429 codes, generic login response |
| Single key versus dual-key rotation | Config shape and rolling-deploy order |
| Implementations had no home; linter gaps | Hasher and token modules live in authentication; new forbidden contracts |
| Alerts without metrics; purge without owner | Pass criteria, log-based events, opportunistic purge plus script |
| Proxy IP, hashing DoS, M0a size, CLI cost, lockout | Trusted proxies, bounded hashing, three M0a PRs, no keychain, break-glass in M5 |

## Shipping reality

The P1 gate and the late bootstrap-admin mean M2 to M4.5 run only in dev and test. First production deploy needs M5. TLS terminates at the ingress (the app assumes HTTPS), CORS is off by default, and reads are not audited (accepted).
