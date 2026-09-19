# Trutina Project Context

## Overview

Trutina is a Python double-entry bookkeeping engine. The repository is a `uv`
workspace, not a single application: `trutina-core` owns the accounting domain,
`trutina-storage-mongo` and `trutina-storage-postgres` each implement its repository
contracts against a different backend, `trutina-config`/`trutina-shared` provide
cross-cutting settings and error/validation primitives, and two independent
presentation apps — `trutina-cli` (Typer/Rich terminal + interactive shell) and
`trutina-api` (FastAPI) — sit on top of the same domain services. This document
explains why the workspace is shaped this way and rolls up what each package's own,
independently-verified `README.md`/`CONTEXT.md` confirms is actually implemented
today. For any package's internal reasoning, see that package's own `CONTEXT.md` —
this file does not restate it.

## Why Split Into a Workspace At All

Two presentation layers (`trutina-cli`, `trutina-api`) need identical business
rules. Keeping the domain in a separate, installable package (`trutina-core`) with
zero storage/transport awareness — rather than folding it into whichever app was
written first — means neither app can accidentally depend on the other's
presentation concerns, and the domain layer never needs to know either exists.
`trutina-storage-mongo` and `trutina-storage-postgres` each exist as their own
package for the same reason: each is one of only two places in the workspace
allowed to import its respective driver (`beanie`/`pymongo`, or
`sqlalchemy`/`asyncpg`), so a repository contract's storage-agnosticism is provable
by import-linter, not just asserted by convention — and proving both contracts are
genuinely backend-agnostic, not Mongo-shaped in disguise, was the explicit reason
`trutina-storage-postgres` was built as a sibling rather than a Mongo-package
subfolder. `trutina-shared` and `trutina-config` sit at the bottom because their
contents (validation rules, the error model, environment-driven settings) are
needed identically by every package above them and have no accounting-specific or
transport-specific shape of their own.

## What Is Genuinely Implemented End-to-End Today

- **Account, journal, and posting domains** — validated schemas, DTOs/ViewModels,
  and all three services (`AccountService`, `JournalService`, `PostingService`)
  are confirmed complete in `trutina-core`'s own README/CONTEXT, not partial.
- **Both storage backends** — concrete `Mongo*Repo` implementations
  (`trutina-storage-mongo`) and concrete `Postgres*Repo` implementations
  (`trutina-storage-postgres`, with Alembic migrations) are confirmed implemented
  and tested independently. **Only PostgreSQL is actually wired into either
  presentation app** — `apps/cli/pyproject.toml` and `apps/api/pyproject.toml` both
  declare `trutina-storage-postgres`, not `trutina-storage-mongo`, as their storage
  dependency. `trutina-storage-mongo` remains in the workspace with its own CI lane
  but is not app-facing today.
- **The CLI** — `account`, `journal`, `posting` Typer command groups are fully
  wired end to end (command → parser/prompt → handler → service → repository),
  with unit and integration test tiers per feature, plus a working interactive
  shell with live tab completion derived from the real Click command tree.
- **The API** — per `apps/api/README.md`/`CONTEXT.md`, the fixed Router → Mapper →
  Handler → Presenter pipeline, eager lifespan-time `Container` composition against
  `trutina-storage-postgres`, and the shared exception-handling seam are all live,
  non-scaffold code for `account`/`journal`/`posting`, with `system` as a documented
  flat exception. `apps/api/README.md` now exists (resolving the prior "no README"
  gap), but it does not enumerate test-tier coverage per feature the way
  `apps/cli`'s documentation does — whether all three features have all five test
  tiers written remains unconfirmed in this pass.
- **Trial balance** — `TrialBalanceService`, `TrialBalanceRepo`, `AccountBalanceEntry`,
  and `TrialBalanceViewModel` in `trutina-core`; `PostgresTrialBalanceRepo` in
  `trutina-storage-postgres` (a `GROUP BY` over `postings`, no migration); the
  `trial-balance` CLI command; and `GET /trial-balance`. All four layers have unit and
  integration tests. All-time or single `as_of_date` cutoff only; accounts without
  postings do not appear; PostgreSQL only.

## What Is Partial or Explicitly Out of Scope

- Reporting beyond the trial balance — period-range or comparative views, financial
  statements, full-chart zero-padded trial balance output, and a MongoDB trial balance
  implementation — are not implemented anywhere in the workspace.
- Import/export or external integration surfaces — not implemented.
- `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status — carried
  forward from prior documentation but **not re-confirmed** against
  `trutina-core`'s current README/CONTEXT in this pass; treat as unconfirmed, not
  as verified fact, until checked directly against source.
- `MongoPostingRepo.save_many()` has no multi-document transaction — an accepted,
  documented gap in `trutina-storage-mongo`'s own CONTEXT.md. No longer app-facing
  risk, since neither presentation app depends on that package today.
- `get_field_violations()` (in `trutina-shared`) downgrades every domain-raised
  `ErrorCode` to `UNKNOWN_ERROR` on `FieldViolation.code`; the real code survives
  only as a string in `FieldViolation.value`. Both `trutina-cli` and `trutina-api`
  document their own recovery logic for this at the presentation layer — this is a
  known, accepted upstream gap, not independently re-fixed by either app.
- The `ACCOUNT_HAS_POSTINGS` account-delete safeguard is wired in
  `AccountService.delete_account()` only when a composition root supplies the
  optional `has_postings` callback — not confirmed whether either app's
  composition root currently does.

## Cross-Package Conflicts Found During This Pass

1. **`default_posting_date()` usage.** `trutina-shared`'s own README and
   CONTEXT.md state `util.default_posting_date()` is "not called anywhere in the
   active workflow today." However, `apps/cli`'s journal parser
   (`cli/features/journal/parser.py`) imports `default_posting_date` from
   `trutina.shared.util` and calls it directly to resolve a blank posting-date
   input. These two verified package docs are stating contradictory facts about
   the same function. **Not resolved here** — needs a direct source check against
   both `packages/shared/src/trutina/shared/util.py` and the CLI parser to
   determine which doc is stale.
2. **API test-tier maturity is now partly resolvable, not fully.** `apps/cli`'s
   own docs explicitly enumerate unit vs. integration test files per feature.
   `apps/api/README.md` now exists (it did not at the time of the prior pass) and
   states the fixed Router → Mapper → Handler → Presenter pipeline and shared
   fixtures (`fake_container`, `api_client`, `real_api_client`) are in place, but
   it does not enumerate, feature by feature, that all three
   (`account`/`journal`/`posting`) actually have all five test tiers written
   today. Treat API test coverage as "designed for and README-documented" rather
   than "tier-by-tier confirmed" until a pass checks each feature's test
   directory directly.
3. **Confirmed syntax defect (previously only flagged).** `apps/api/CONTEXT.md`
   now states, against live source, that `_fill()` in
   `api/shared/errors/handlers.py` uses `except KeyError, IndexError:`, which is
   invalid Python 3 syntax (`except (KeyError, IndexError):` is required), and
   would raise `SyntaxError` at import time as written. This resolves the prior
   version of this document's open question of whether it was a live bug or a
   capture artifact — it is confirmed live. **Not yet fixed** — carried forward
   as an item for `ROADMAP.md`.
4. **Root import-linter storage-layer naming — resolved in this pass.**
   `apps/cli/CONTEXT.md` and `apps/api/CONTEXT.md` both flagged that the root
   `pyproject.toml`'s import-linter `layers` contract "still names its storage
   layer `trutina.storage_mongo`" while each app's own `pyproject.toml` depends on
   `trutina-storage-postgres`. Checked directly against the current root
   `pyproject.toml` in this pass: the `layers` contract already reads
   `"trutina.storage_mongo | trutina.storage_postgres"` — both backends are
   named as parallel members of the same layer. `ARCHITECTURE.md` and `AGENTS.md`
   have been corrected to reflect this and to state explicitly that only
   `trutina-storage-postgres` is consumed by either app today. This flag is
   closed.
5. **Root `compose.yml`/`compose.dev.yml` still MongoDB-only.** Both files
   provision and sync only MongoDB/`trutina-storage-mongo` paths — no PostgreSQL
   service, no `trutina-storage-postgres` sync/rebuild targets — despite
   `apps/api`'s and `apps/cli`'s real dependency on `trutina-storage-postgres`.
   Confirmed against the current file contents in this pass. **Not resolved
   here** — infra file changes are out of scope for a documentation pass; tracked
   in `ROADMAP.md`.

## Testing Strategy (cross-cutting)

Every package/app's tests are collected from one root `pytest.ini`
(`testpaths = tests apps packages`), with a mandatory three-axis marker
discipline enforced by root `conftest.py`: a hand-written speed marker
(`unit`/`integration`), an automatically-derived layer marker
(`core`/`infra`/`cli`/`api`/`shared`/`config`, derived from file path — never
hand-written), and, for `infra`-layer tests only, an automatically-derived backend
marker (`mongo`/`postgres`, derived from which storage package's directory the
test lives under). This lets `pytest -m "unit and cli"` or
`pytest -m "integration and infra and postgres"` remain trustworthy filters
instead of decorative metadata that could silently drift from where a test
actually lives. Root `tests/` holds only shared fixtures/factories/fakes; every
package/app's real test cases live beside its own code.

## Long-Term Direction

- Confirm and, if needed, correct the `default_posting_date()` conflict above.
- Fix the confirmed `except KeyError, IndexError:` defect in
  `api/shared/errors/handlers.py`.
- Update root `compose.yml`/`compose.dev.yml` to provision PostgreSQL, matching
  what `apps/api`/`apps/cli` actually depend on.
- Confirm `apps/api/README.md`'s test-tier coverage feature-by-feature, the way
  `apps/cli/README.md` already does for the CLI.
- Extend reporting beyond the trial balance (full-chart output, period ranges,
  financial statements).
- Add import/export and external integration surfaces once reporting exists.
- Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status
  directly against current `trutina-core` source.
