# M5 — Authorization

## Milestone record

### M5 — Authorization

- Create `trutina-authorization`; `Policy.is_allowed(identity, action, resource)`
- Own Phase 0: an accounting-specific permission matrix
- `bootstrap-admin`: the "only if no users exist" rule lives in the service, the repository offers an atomic primitive guarded by `pg_advisory_xact_lock`, with a two-concurrent-calls test
- Break-glass: an offline `tools/` command, using direct database access, to create an admin or reset a password for lockout recovery
- Decide whether public registration exists and read routes load the access state per request (settled by ADR 0001: yes, session validation already does); add the 403 error code
- Apply step-up (ADR 0002) to user and role management, and review the session lifetimes and the step-up window

## Milestone summary

**M5**
Outcome: Roles and a permission matrix are enforced; only then can the API be deployed. Status: not started. Gate: the P1 gate is satisfied only here.

## Cards

### WP M5-A: Design

### M5.0 — Permission matrix

**Needs:** M4a.3

#### Spec

- **Scope:** Accounting-specific matrix as the milestone's Phase 0.
- **Excludes:** No code.
- **Needs:** M4a.3
- **Accept:**
  - [ ] Matrix reviewed; default is deny.

#### Outcome

Evidence: Reviewed doc


---

### M5.6 — Open decisions record

**Needs:** M5.0

#### Spec

- **Scope:** Decide public registration, read routes load the access state per request (settled by ADR 0001: yes, session validation already does), single-tenant revisit, and the review of the session lifetimes and step-up window (ADR 0002).
- **Excludes:** No code.
- **Needs:** M5.0
- **Accept:**
  - [ ] Each decision recorded with its reason.

#### Outcome

Evidence: Plan edit

---

### WP M5-B: Package and roles

### M5.1 — `trutina-authorization` scaffold

**Needs:** M5.0

#### Spec

- **Scope:** New package, `Policy.is_allowed(identity, action, resource)`; import-linter contracts; `_PACKAGE_MARKERS` and `pytest.ini` entries; `check-lane-coverage.sh` and workflow lanes; Dockerfile manifest COPY line and watch entries; docs.
- **Excludes:** No role storage, no route enforcement.
- **Needs:** M5.0
- **Accept:**
  - [ ] `lint-imports` passes with the new contracts and a manual negative check fails as expected.
  - [ ] The lane covers its tests.

#### Outcome

Evidence: G0, G-DOCKER


---

### M5.2 — Roles in the access state

**Needs:** M5.1

#### Spec

- **Scope:** `role` on `AccessState`, users-role migration with tested downgrade, status checker returns it.
- **Excludes:** No enforcement.
- **Needs:** M5.1
- **Accept:**
  - [ ] Existing users get a defined safe default role.
  - [ ] Migration round trip and `alembic check` clean.

#### Outcome

Evidence: G0, G-DOCKER, `alembic check`

---

### WP M5-C: Enforcement and recovery (parallel after M5.2)

### M5.3 — Enforce policy in the API

**Needs:** M5.2, M4a.3

#### Spec

- **Scope:** Register the policy (satisfies P1), enforce per the matrix, add the 403 code with catalogs and parity.
- **Excludes:** No CLI enforcement.
- **Needs:** M5.2, M4a.3
- **Accept:**
  - [ ] A user without a role gets 403 on every business route.
  - [ ] No path makes an authenticated user an administrator by default (test).

#### Outcome

Evidence: G0, lane api


---

### M5.4 — `bootstrap-admin`

**Needs:** M5.2

#### Spec

- **Scope:** Service holds the only-if-no-users rule; repo offers an atomic primitive guarded by `pg_advisory_xact_lock`.
- **Excludes:** No public route.
- **Needs:** M5.2
- **Accept:**
  - [ ] Two concurrent calls create exactly one administrator.

#### Outcome

Evidence: G0, lane infra postgres


---

### M5.5 — Break-glass command

**Needs:** M5.2

#### Spec

- **Scope:** Offline `tools/` command with direct database access to create an admin or reset a password.
- **Excludes:** Not a service or route.
- **Needs:** M5.2
- **Accept:**
  - [ ] Recovers a locked-out system in a documented procedure tested on a scratch database.

#### Outcome

Evidence: G0, documented run

---

### WP M5-D: Release verification

### M5.7 — Release gate verification

**Needs:** M5.3 to M5.6, M4c.2, M4.5.3

#### Spec

- **Scope:** Walk gates R1 to R5 below with evidence; update ROADMAP, ARCHITECTURE and package docs.
- **Excludes:** No new behavior.
- **Needs:** M5.3 to M5.6, M4c.2, M4.5.3
- **Accept:**
  - [ ] Every gate item has linked evidence.

#### Outcome

Evidence: G0, G-DOCKER, R-gates
