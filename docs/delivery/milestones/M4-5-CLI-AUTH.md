# M4.5 — CLI auth

## Milestone record

### M4.5 — CLI auth group

- `trutina-cli auth login`, `auth logout`, `auth whoami`; a registered group, so one-shot dispatch works
- Email prompt, then hidden password prompt; never a `--password` flag; bypass prompt_toolkit history in the shell
- CLI sessions are opaque, database-backed tokens from the same `sessions` table and session service as the API (ADR 0001, D34), with the `cli` client kind, 14 days idle and 30 days absolute, validated against the CLI only and with no step-up, because the CLI is an operator tool that already holds the database URI (ADR 0002, D35); there is no signing key (P5)
- Session stored in a `0600` file with a warning (keychain support deferred); `TRUTINA_AUTH_TOKEN` takes precedence for headless use, with output redaction
- Logout deletes the local session and revokes it server-side
- CLI actor is `str(subject_id)` and the fixed CLI `PRE_AUTH_ACTOR` is deleted; dev and test users come from a `tools/` seed script and factories
- CLI auth is attribution-only, since the CLI already holds the database URI; its audit rows are untrusted

## Milestone summary

**M4.5**
Outcome: The CLI acts as an authenticated user, attribution only (decision 9). Status: not started. Gate: parallel to M4a to M4c once M3.4 is done.

## Cards

### WP M4.5-A: Server-side sessions

### M4.5.1 — Opaque CLI session store

**Needs:** M2.8 (done), M3.3 (done), M3.4 (done; D1 settled by ADR 0001)

#### Spec

- **Scope:** Reuse the M3 `sessions` table and session service for the CLI: use the `cli` client kind with its own lifetimes (settled in ADR 0002) and add the CLI-specific issue and revoke paths. No new table unless M3.3's shape cannot carry the CLI. There is no signing key (P5, ADR 0001).
- **Excludes:** No CLI commands.
- **Needs:** M2.8 (done), M3.3 (done), M3.4 (done; D1 settled by ADR 0001)
- **Accept:**
  - [ ] Session issue, validate and revoke pass against real PostgreSQL.
  - [ ] Migration round trip and `alembic check` clean.

#### Outcome

Evidence: G0, G-DOCKER, `alembic check`

---

### WP M4.5-B: CLI surface

### M4.5.2 — `auth` command group

**Needs:** M4.5.1

#### Spec

- **Scope:** `auth login`, `logout`, `whoami` as a registered group; email prompt then hidden password prompt, never a `--password` flag, prompt_toolkit history bypassed in the shell; session in a `0600` file with a warning; `TRUTINA_AUTH_TOKEN` takes precedence with output redaction; logout deletes the local file and revokes server-side; CLI `ERRORS`, `HINTS`, `FIELD_LABELS` entries.
- **Excludes:** No actor swap (M4.5.3).
- **Needs:** M4.5.1
- **Accept:**
  - [ ] A password never appears in history, output or logs.
  - [ ] Session file has mode 0600 where the OS supports it.
  - [ ] One-shot dispatch of `auth` works.

#### Outcome

Evidence: G0, lane cli

---

### WP M4.5-C: Attribution

### M4.5.3 — CLI actor and seed script

**Needs:** M4.5.2, M1c.1

#### Spec

- **Scope:** CLI actor becomes `str(subject_id)`; delete the CLI `PRE_AUTH_ACTOR`; format check; a `tools/` seed script and factories for dev and test users.
- **Excludes:** No enforcement of authorization in the CLI.
- **Needs:** M4.5.2, M1c.1
- **Accept:**
  - [ ] Actor reaches `created_by` and `audit_events` in a CLI integration test.
  - [ ] Documented that CLI audit rows are untrusted and that the CLI is an operator tool with no step-up.

#### Outcome

Evidence: G0, lane cli integration
