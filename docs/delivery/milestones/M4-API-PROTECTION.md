# M4 — API protection

## Milestone record

### M4a — Protect the endpoints

- All 12 business endpoints (accounts 5, journal entries 3, postings 3, trial-balance 1) protected by router-level `Depends()`
- Route-inventory test: every route outside an explicit public allowlist carries the auth dependency. Allowlist: 2 `system`, 2 `auth`, and `/docs`, `/redoc`, `/openapi.json` only where the docs flag is on (public in dev and test, disabled elsewhere) (P7)
- Step-up (ADR 0002): a `require_recent_auth` dependency on `POST /postings/{journal_number}` and `DELETE /accounts/{code}`; account update is decided here or in M5.0
- Deploy gate (P1): the API refuses to start with auth enabled outside dev and test until an authorization policy is registered

### M4b — Actor in the API

- API handlers pass `actor=str(identity.subject_id)` to every write service: handlers gain an `actor` parameter supplied by the router, the fixed API `PRE_AUTH_ACTOR` is deleted, and the UUID-or-`system:` format check lands here
- Authenticated test client fixture and a `get_current_identity` override, so existing router tests do not all return 401

### M4c — Load and pool check

- Load test including hashing cost, re-auth rate, the per-request session lookup and the per-write status check; tune `pool_size`
- Write down the expected load first (concurrent users, writes per minute); the test has nothing to pass against without it
- Provisional targets: status-check p95 under 20 ms, pool wait p95 under 50 ms. Record a baseline on real PostgreSQL, revise once from the data, then freeze them as load-test pass criteria; they become alerts only once a metrics path exists (none does today)
- Tune the pool: the default is `pool_size` 1 with `max_overflow` 10, and the status check adds one query to every write

## Milestone summary

**M4a**
Outcome: Every business route requires authentication, and the API cannot start in a deployed environment without an authorization policy. Status: not started. Gate: M4a.2 and M4b.1 merge back to back; neither alone is releasable.

**M4c**
Outcome: Measured capacity and a tuned pool. Status: not started. Gate: no deploy gate; findings feed M5.7.

## Cards

### WP M4a-A: Identity dependency

### M4a.1 — Identity dependency and authenticated test client

**Needs:** M3.7

#### Spec

- **Scope:** `get_current_identity` and the authenticated client fixture and override, so existing router tests do not return 401. Sequencing correction: the plan placed this fixture in M4b, but protecting routes without it would leave the suite red; no decision changes.
- **Excludes:** No route protection yet.
- **Needs:** M3.7
- **Accept:**
  - [ ] Existing router tests pass using the override.
  - [ ] An unauthenticated client is rejected with 401 on a test route.

#### Outcome

Evidence: G0, lane api

---

### WP M4a-B: Protection and gate (parallel after M4a.1)

### M4a.2 — Protect the 12 business endpoints

**Needs:** M4a.1

#### Spec

- **Scope:** Router-level `Depends()` on accounts (5), journal entries (3), postings (3), trial-balance (1); docs-enabled flag in `ApiSettings` (P7); route-inventory test; the step-up dependency on posting and account delete (ADR 0002).
- **Excludes:** No actor change (M4b.1).
- **Needs:** M4a.1
- **Accept:**
  - [ ] Every route outside the allowlist (2 system, 2 auth, docs routes only where the flag is on) carries the dependency (test fails otherwise).
  - [ ] Docs routes are disabled in the default production environment.
  - [ ] A session older than the window gets 403 `AUTH_REAUTH_REQUIRED` on posting and account delete and nothing is written; reads and journal entry creation are unaffected.

#### Outcome

Evidence: G0, lane api


---

### M4a.3 — Deploy gate (P1)

**Needs:** M3.6

#### Spec

- **Scope:** Outside dev and test the API refuses to start until an authorization policy is registered; no auth-disabled mode. Compose and smoke script run the API in a non-production environment so Docker smoke still passes.
- **Excludes:** No policy implementation (M5).
- **Needs:** M3.6
- **Accept:**
  - [ ] Production environment without a policy fails startup; dev and test start.
  - [ ] Docker smoke passes with the new settings.

#### Outcome

Evidence: G0, G-DOCKER

---

### WP M4a-C: Actor in the API

### M4b.1 — API handlers pass the real actor (milestone M4b)

**Needs:** M4a.2, M1c.2

#### Spec

- **Scope:** Handlers gain an `actor` parameter supplied by the router as `str(identity.subject_id)`; delete the API `PRE_AUTH_ACTOR`; add the UUID-or-`system:` format check (D4).
- **Excludes:** No CLI change (M4.5).
- **Needs:** M4a.2, M1c.2
- **Accept:**
  - [ ] An authenticated write records the caller's UUID in `created_by` and `audit_events` (end-to-end).
  - [ ] No `PRE_AUTH_ACTOR` reference remains in the API (grep).

#### Outcome

Evidence: G0, lane api integration

---

### WP M4c-A: Load

### M4c.1 — Write down expected load

**Needs:** owner: you; may start now. Pulled forward by ADR 0001: it also sizes the session-lookup pool for M3.3

#### Spec

- **Scope:** Concurrent users and writes per minute, recorded in this plan.
- **Excludes:** No testing.
- **Needs:** owner: you; may start now. Pulled forward by ADR 0001: it also sizes the session-lookup pool for M3.3
- **Accept:**
  - [ ] Numbers are recorded and referenced by M4c.2.

#### Outcome

Evidence: Reviewed plan edit


---

### M4c.2 — Load test and pool tuning

**Needs:** M4b.1, M4c.1

#### Spec

- **Scope:** Include hashing cost (login and re-authentication), the per-request session lookup and the per-write status check; fire more concurrent authenticated requests than the pool size to prove no stall; measure `pool_pre_ping` cost and set `pool_timeout_s`; baseline on real PostgreSQL; tune `pool_size` (default 1, overflow 10); revise provisional thresholds once (status check p95 under 20 ms, pool wait p95 under 50 ms), then freeze as pass criteria.
- **Excludes:** No metrics or alerting path.
- **Needs:** M4b.1, M4c.1
- **Accept:**
  - [ ] Baseline and tuned results recorded; thresholds frozen.
  - [ ] Pool settings updated in config docs.

#### Outcome

Evidence: Recorded load-test results
