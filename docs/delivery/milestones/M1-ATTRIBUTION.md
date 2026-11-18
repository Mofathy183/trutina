# M1 — Attribution

## Milestone record

### M1a — Actor plumbing and `created_by` (done)

- **Ticket 1 done** (issue #51, PR #53 merged as commit `555430e`, 9 checks green, branch deleted): a required keyword-only `actor` on `create_journal_entry` and `post_journal_entry`, checked first via `trutina-shared` (D12), with fixed per-app constants (D13). Verified before merge: 1383 unit tests and 77 integration tests (core, api, cli) pass, `lint-imports` keeps all 8 contracts, and an AST audit found no caller without `actor`. Docs updated in the same PR. At that point the actor was validated and dropped; ticket 2 stores it. M1a was split into two tickets because the whole change is too large for one PR
- **Ticket 2 done** (issue #52, PR #54, merge commit `e9dd41b`, branch `feat/persist-created-by`, CI green): every new journal entry and posting records its writer as `created_by` in PostgreSQL. Delivered as one PR rather than the two the ticket allowed for
- Migration `a3f1c9d2b7e4`, on top of the then-head `7e1b970f05a7`: nullable `created_by` text column on `journal_entries` and `postings`, no default and no foreign key, so it is a metadata-only change with no backfill. Null means written before attribution. The downgrade is tested by a round trip that restores head in a `finally` block
- Contracts: `JournalRepo.save(entry, *, created_by)` and `PostingRepo.save_many(postings, *, created_by)` take a required keyword-only `created_by`. Both services pass their `actor` through unchanged. It is not a field of `JournalEntry`, `LedgerPosting` or any view model, so reads never return it, and it is still never logged
- PostgreSQL adapters (D15): `created_by` is written once on the `journal_entries` row and on every `postings` row in a batch. `journal_lines` has no column; lines inherit their entry's attribution. `_to_domain()` never reads it
- Fakes: `FakeJournalRepo.saved_created_by` (one value per `save`) and `FakePostingRepo.saved_created_by` (one value per `save_many` call, not per posting)
- Mongo is frozen (D14): both adapters accept `created_by` to satisfy the contracts and do not store it. Each Mongo repository has a test that the call succeeds and the raw document has no `created_by` field, so the behavior is pinned as deliberate. The Mongo README and CONTEXT carry a "Frozen" section (history: the Mongo package was deleted later, issue #60, PR #62)
- Tests added: model tests for both tables; a migration round-trip test; service tests that the actor reaches the repository unchanged, that a blank actor records nothing and that a batch records one value; handler tests for all four handlers (API and CLI, journal create and posting post) asserting each app's `PRE_AUTH_ACTOR` reaches the repository through the fake's hook; and one end-to-end test that writes through the real services and reads both columns back with raw SQL, using different actors for the entry and the postings. The repository, trial balance and Mongo integration tests were updated for the new keyword
- Docs updated in the same PR: core, API, CLI, storage-postgres, storage-mongo, ARCHITECTURE, AGENTS, PROJECT_CONTEXT and ROADMAP no longer say the actor is "validated and dropped"
- Until auth ships, CLI and API each pass their own fixed constant (`system:pre-auth:cli`, `system:pre-auth:api`), so no new row is ever null. The UUID-or-`system:` format check is deferred to M4b, when a real value first exists; handlers keep their signatures until then (D12, D13)
- Not part of M1a: account writes and `audit_events` (M1c), a users table (M1b), and any CHECK constraint or format check on `created_by`

### M1b — Users (Done)

- **Implemented and Done**, passing every local gate: `tools/pre-push.sh` (format, lint, `ty`, 8 import contracts, marker hygiene, lane coverage, unit tests), the unit and integration lanes for authentication and storage-postgres, and `alembic upgrade head`, `alembic check` (no new operations) and `tools/docker-smoke.sh` run end to end (image build, all four migrations from an empty database, API health, structured logging). The new migration is `373da73ec0bb`, on top of `a3f1c9d2b7e4`. Delivered as seven commits for one squash-merged PR: error codes; `normalize_email`, the `User` validator and `set_active`; fakes and `make_user`; users model, migration, `PostgresUserRepo` and tests; API and CLI catalog entries with a parity test per app; Docker manifest, reload and watch entries; docs. Issue #55, PR #56, merge commit `fb541c2`, all CI checks passed, branch `feat/55-postgres-users-store` deleted
- **Done:** `alembic -c packages/storage-postgres/alembic.ini check` reports no new upgrade operations, so the model and the migration agree. A `git grep` of `UserRepo` lists only the contract, its fake and the fixture; it skips untracked files, so the new `identity/` folder, the migration and the new tests must be added to git before the PR is opened
- **Done:** `tools/docker-smoke.sh` passes locally: the image builds with the authentication manifest COPY line, Postgres starts, migrations apply through `373da73ec0bb` from an empty database, the API reports healthy and the structured logging check passes. On Windows Git Bash it needs `MSYS_NO_PATHCONV=1`, which stops the shell rewriting `/app/...` arguments, and host port 8000 must be free (a leftover compose container held it on the first run). CI's Ubuntu run remains the authoritative check
- The parity tests exclude `REQUEST_VALIDATION_ERROR` by name in each app, since neither catalogs it
- PostgreSQL only; Mongo is untouched (D14). No routes, commands, hasher or login in this milestone
- `trutina-shared`: `ErrorCode` members `DUPLICATE_USER_EMAIL = "user.duplicate_email"` and `UNKNOWN_USER = "user.unknown"`, in a new user group (D19)
- `trutina-authentication`: `normalize_email()` (strip, then `casefold()`) exported from the package root; `User.email` gets a normalizing validator, so every constructed user is already normalized; `UserRepo` gains `set_active(user_id, is_active)`. Contract docstrings: `create` ignores `created_at` and raises `DUPLICATE_USER_EMAIL`; `get_by_email` normalizes its argument; `set_active` and `update_password_hash` raise `UNKNOWN_USER` on a miss (D16 to D18). No email format validation yet
- `trutina-storage-postgres`: an `identity/` folder (`model.py`, `repository.py`, `__init__.py`). Table `users`: `id` UUID primary key supplied by the application, `email` text not null with `uq_users_email`, `password_hash` text not null (D20), `is_active` boolean not null defaulting to true, and `TimestampedMixin`. No `email_key` column (D16)
- `PostgresUserRepo`: `create`, `get_by_id`, `get_by_email`, `update_password_hash`, `set_active`. `_to_domain()` builds a real `User`; `_on_duplicate()` maps `uq_users_email` to `DUPLICATE_USER_EMAIL` and anything else to `UNKNOWN_ERROR`. `created_at` is read from the database (D17)
- `DUPLICATE_USER_EMAIL` is raised with context `resource` and `field` only, never the email value, because `AppError.context` reaches logs and the API catalog interpolates it (D19). Do not use `AppError.conflict()`, which requires a value
- Wiring: `alembic/env.py` imports `UserModel` (otherwise autogenerate and `alembic check` cannot see the table); own migration on top of `a3f1c9d2b7e4` with a tested downgrade; the storage package's `pyproject.toml` gains `trutina-authentication` and its workspace source, and `uv.lock` is regenerated
- Apps, error entries only: API catalog entries (409 and 404, with no interpolated value in either message), CLI `ERRORS`, `HINTS` and `FIELD_LABELS` entries, and the every-code-has-both parity test, all in the same PR
- Docker: the API `Dockerfile` needs the authentication manifest COPY line and `compose.dev.yml` its watch entry. M0a-C deferred these to the milestone that introduces the dependency, and this is that milestone; without them the docker smoke job fails
- Test infrastructure: `users` added to the `clean_pg_db` truncate list; a `postgres_user_repo` fixture; `FakeUserRepo.set_active`, and `update_password_hash` raising `UNKNOWN_USER` instead of a bare `KeyError`; `tests/factories/user.py` with `make_user`
- Tests: `normalize_email` and normalize-on-construct; model and mapping unit tests; integration for create, both lookups (email case-insensitive), a duplicate email in two casings raising `DUPLICATE_USER_EMAIL` with no email in its context, both mutators, unknown user raising `UNKNOWN_USER`, and a caller-supplied `created_at` being ignored; a migration round trip that restores head in a `finally` block
- Acceptance: `alembic check` clean; `lint-imports` keeps all 8 contracts, with a manual negative check that authentication importing storage fails; ruff, `ty`, unit and integration lanes, `check-lane-coverage.sh` and docker smoke green; a `git grep` audit of every `UserRepo` implementer and caller (`ty` misses untyped fixtures); no Mongo file changed; squash-merge only, with the repository setting enabled first
- Docs in the same PR: storage-postgres and authentication README and CONTEXT, shared CONTEXT, ARCHITECTURE, AGENTS (dependency tables and layout), PROJECT_CONTEXT and ROADMAP. The authentication docs stop saying there is no storage adapter
- Not part of M1b: the register use case and hasher implementation (M2), refresh tokens (M3), `audit_events` (M1c), and email format validation

### M1c — Actor on account writes (P6) (Done)

- **Ticket M1c.1 done** (issue #57, PR #61, merge commit `d433a5a`, branch `feat/57-account-write-actor`, CI green): `AccountService.create_account`, `update_account` and `delete_account` take a required keyword-only `actor`, checked first with `is_non_blank_actor` (D12), so a blank actor performs no repository call and wins over unknown-account, duplicate-code, duplicate-name and `ACCOUNT_HAS_POSTINGS` errors. The service passes it unchanged to `AccountRepo.create`, `update` and `delete_by_code` as a required keyword-only `created_by`; on update and delete it names the caller performing that write, not the account's original creator
- Intermediate state (R3), resolved by M1c.2: `PostgresAccountRepo` accepted `created_by` and did not store it, so account changes were unattributed between M1c.1 and M1c.2. The actor is never logged and never placed in `AppError.context`
- `FakeAccountRepo` records `created_by_on_create`, `created_by_on_update` and `created_by_on_delete`, each index-aligned with `created_accounts`, `updated_accounts` and `deleted_codes` and written on success only. API and CLI account handlers pass their own `PRE_AUTH_ACTOR` (D13); handler signatures are unchanged
- Tests: blank actor on all three methods with no repository call, precedence over the other errors, pass-through, and no actor in any log record; handler tests per app; Postgres repository tests updated. The caller audit found only test seeding code missing the keyword (five files, twelve call sites); the production callers were the two handlers. Verified before merge: 1482 unit tests; integration api 28, cli 34, infra postgres 67, core 15; `check-lane-coverage.sh` OK; ruff, `ty` and `lint-imports` clean
- Scope amendment, owner decision: the Mongo account adapter and its pinning tests were left out of M1c.1 because Mongo was frozen; the package was then deleted under issue #60 (see D14)
- **Ticket M1c.2 done** (issue #58, PR #63, merge commit `b76dcd3`, branch `feat/58-account-audit-events`, 11 commits, 8 of 8 checks green): every account create, update and delete writes one `audit_events` row in the same session and the same single commit as the account change, so the two persist together or not at all. A call that raises writes no row, and an update that changes nothing still writes one
- Table and migration: `41065b2e2190` on top of `373da73ec0bb`, with a tested downgrade that drops the table. Columns `id` (bigint, autoincrement), `entity`, `entity_key` (the account code), `action`, `actor` and `occurred_at` (`timestamptz`, stamped by PostgreSQL), all NOT NULL. No foreign key, so a delete can still be recorded; no `updated_at`, no payload and no indexes. `ck_audit_events_action` restricts `action` to the `AuditAction` values `create`, `update` and `delete`. `AuditEventModel` is imported in `alembic/env.py`; `audit_events` is in the `clean_pg_db` truncate list (D21)
- Error mapping: a rejected audit insert surfaces as `UNKNOWN_ERROR` and rolls the account write back. The delete path gained its own `IntegrityError` translation, because nothing in it could violate a constraint before. The stale `PostgresAccountRepo._on_duplicate` docstring was corrected in the same PR
- Tests: model unit tests; a downgrade and upgrade round trip that restores head in a `finally` block; 11 integration tests on real PostgreSQL (5 for rows written, 3 for rejected writes leaving no row, 3 for rollback through the real CHECK constraint on create, update and delete). Verified before merge: 1355 unit tests; integration infra postgres 79, core 15, api 28, cli 34; `check-lane-coverage.sh` OK; ruff, `ty` and `lint-imports` (7 contracts) clean; `alembic check` clean; Docker smoke applying all five migrations from an empty database
- Not part of M1c.2: a read API, a retention policy, an actor format check (M4b.1), journal or posting audit, before and after values, and database-level append-only enforcement (D22)
- Account create, update and delete take the same required `actor: str`. A column cannot record a delete, so an append-only `audit_events` table (entity, key, action, actor, time) is written by the Postgres repo in the same transaction as the write; own migration
- `audit_events` is Postgres-only; PostgreSQL is the only storage backend since the Mongo retirement (D14 superseded)
- Acceptance test: a failed `audit_events` insert rolls back the account write
- Lands before M4b, because API handlers pass an actor to every write route

## Milestone summary

**M1b**
Outcome: A PostgreSQL user store exists. Status: done (issue #55, PR #56, merge commit `fb541c2`). Gate: squash-merge with CI green.

**M1c**
Outcome: Every account create, update and delete records its actor in an audit trail. Status: M1c done (M1c.1 and M1c.2 merged). Gate: met; M1c merged before M4b.

## Cards

### WP M1b-A: Landing

### M1b.1 — Open and land the M1b PR

**Labels:** Done
**Package:** storage-postgres, authentication, shared, api, cli
**Needs:** none; implementation is complete
**Decisions / Gaps:** D16, D17, D18, D19, D20

#### Spec

- **Scope:** Add untracked files (`identity/`, migration `373da73ec0bb`, tests) to git, open the PR, enable squash-only merging first, merge.
- **Excludes:** No new behavior or edits to D16 to D20.
- **Needs:** none; implementation is complete
- **Accept:**
  - [ ] CI is green on all checks including the Docker smoke job.
  - [ ] `git grep UserRepo` lists every implementer and caller, none missing.
  - [ ] Merged as one squash commit.

#### Outcome

Issue #55 closed. PR #56 merged to `main` as merge commit `fb541c2` (branch `feat/55-postgres-users-store` deleted, all CI checks passed).

Evidence: G0, G-DOCKER, `alembic check` clean

---

### WP M1c-A: Contract and plumbing

### M1c.1 — Required actor on account write services

**Labels:** Done
**Package:** core, storage-postgres, api, cli
**Needs:** M1b.1 (not required; ran in parallel)
**Decisions / Gaps:** D12, D15, R3

#### Spec

- **Scope:** Purpose: forgetting an actor becomes a type error. Required keyword-only `actor` on `AccountService` create, update and delete, checked first with `is_non_blank_actor` (D12). Repo contract gains keyword-only `created_by` (D15 pattern). Delivered in core, the fake (per-method `created_by_on_*` hooks), `PostgresAccountRepo` (accepts, does not store), and the API and CLI account handlers passing their fixed `PRE_AUTH_ACTOR`. Intermediate state per R3: the actor is validated and passed to the repo, not yet stored.
- **Excludes:** No audit table, no format check (D4), no signature change to handlers, no change to the Mongo account adapter (owner decision; Mongo was frozen, then deleted under issue #60).
- **Needs:** M1b.1 (not required; ran in parallel)
- **Accept:**
  - [ ] Met: a blank or whitespace actor raises `REQUIRED_FIELD` on `actor` for create, update and delete, and the fake records no call.
  - [ ] Met: a blank actor wins over unknown-account, duplicate-code, duplicate-name and `ACCOUNT_HAS_POSTINGS`, and the postings predicate is not called.
  - [ ] Met: a valid actor reaches the fake unchanged on all three writes; each API and CLI handler passes its own `PRE_AUTH_ACTOR`.
  - [ ] Met: caller audit complete; `delete_account` tests with and without `has_postings` still pass; no actor in any log record.
  - [ ] Dropped: the Mongo pinning criterion, by owner decision.

#### Outcome

Issue #57 closed. PR #61 merged to `main` as merge commit `d433a5a` (branch `feat/57-account-write-actor`, CI green). Unblocks M1c.2 and M4.5.3.

Evidence: G0, lanes core, api, cli, infra

---

### WP M1c-B: Audit persistence

### M1c.2 — `audit_events` table written in the same transaction

**Labels:** Done
**Package:** storage-postgres
**Needs:** M1c.1 (done)
**Decisions / Gaps:** D3, D5, D15, D21, D22, R3

#### Spec

- **Scope:** Append-only `audit_events` (entity, key, action, actor, time), own migration on the then-head `373da73ec0bb` with a tested downgrade, written by the Postgres account repo inside the write transaction. Added to the `clean_pg_db` truncate list. Postgres only (D5). Also corrected the stale `PostgresAccountRepo._on_duplicate` docstring (known gap closed), since this ticket edited that file. Table shape is D21; the append-only limit is D22.
- **Excludes:** No read API for audit rows, no format check, no change to `PostgresExecutor` or the repository contract.
- **Needs:** M1c.1 (done)
- **Accept:**
  - [ ] Met: create, update and delete each write exactly one audit row, delete included, and the delete row is readable after the account row is gone.
  - [ ] Met: a forced failure of the audit insert (a row violating `ck_audit_events_action`) rolls back the account create, update and delete.
  - [ ] Met: a rejected write (duplicate code, unknown account) writes no audit row.
  - [ ] Met: `alembic check` is clean and the migration round trip restores head in a `finally` block.

#### Outcome

Issue #58 closed. PR #63 merged to `main` as merge commit `b76dcd3` (branch `feat/58-account-audit-events`, 11 commits, 8 of 8 checks green). Migration `41065b2e2190`. Unblocks M4b.1 together with M4a.2.

Evidence: G0, G-DOCKER, `alembic check`
