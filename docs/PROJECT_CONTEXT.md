# Trutina Project Context

## Overview

Trutina is a Python double-entry bookkeeping engine. The repository is a `uv`
workspace, not a single application: `trutina-core` owns the accounting domain,
`trutina-storage-mongo` and `trutina-storage-postgres` each implement its repository
contracts against a different backend, `trutina-config`/`trutina-shared` provide
cross-cutting settings and error/validation primitives, `trutina-observability`
provides shared logging configuration and request/command correlation, and two
independent presentation apps — `trutina-cli` (Typer/Rich terminal + interactive
shell) and `trutina-api` (FastAPI) — sit on top of the same domain services. This
document explains why the workspace is shaped this way and rolls up what each
package's own, independently-verified `README.md`/`CONTEXT.md` confirms is actually
implemented today. For any package's internal reasoning, see that package's own
`CONTEXT.md` — this file does not restate it.

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
by import-linter, not just asserted by convention. `trutina-observability` exists
as its own package for a parallel reason: both presentation apps need the identical
formatter chain, redaction, and correlation-id handling, and building that twice
would have been exactly the "N independently drifting copies of the same rule"
failure mode the rest of the workspace's architecture already avoids for business
logic. `trutina-shared` and `trutina-config` sit at the bottom because their
contents (validation rules, the error model, environment-driven settings) are
needed identically by every package above them and have no accounting-specific or
transport-specific shape of their own.
`trutina-authentication` exists as its own package so that identity and
authentication vocabulary never enters `trutina-core`: the accounting domain sees
only an opaque `actor: str`. It sits beside core in the import-linter layers
contract (independent siblings), so neither can import the other.

## What Is Genuinely Implemented End-to-End Today

- **Account, journal, and posting domains** — validated schemas, DTOs/ViewModels,
  and all three services (`AccountService`, `JournalService`, `PostingService`)
  are confirmed complete in `trutina-core`'s own README/CONTEXT, not partial.
  Each also logs one success event through stdlib `logging` after a
  state-changing write persists.
- **Both storage backends** — concrete `Mongo*Repo` implementations
  (`trutina-storage-mongo`) and concrete `Postgres*Repo` implementations
  (`trutina-storage-postgres`, with Alembic migrations) are confirmed implemented
  and tested independently. **Only PostgreSQL is actually wired into either
  presentation app** — `apps/cli/pyproject.toml` and `apps/api/pyproject.toml` both
  declare `trutina-storage-postgres`, not `trutina-storage-mongo`, as their storage
  dependency. `trutina-storage-mongo` remains in the workspace with its own CI lane
  but is not app-facing today. Both backends' `connect()`/`disconnect()` now log
  `db.connected`/`db.disconnected` through stdlib `logging`, never the connection
  URI.
- **`trutina-observability`** — a shared package providing `configure_logging()`,
  `correlation_scope()`, and `CorrelationIdMiddleware`, consumed by exactly the two
  presentation apps. Every other package (core, shared, config, both storage
  backends) emits through plain `logging.getLogger(__name__)` calls with zero
  dependency on this package, enforced by two import-linter contracts. Fully
  tested (40 unit tests as of its initial build), with its own README/CONTEXT.
- **The CLI** — `account`, `journal`, `posting` Typer command groups are fully
  wired end to end (command → parser/prompt → handler → service → repository),
  with unit and integration test tiers per feature, plus a working interactive
  shell with live tab completion derived from the real Click command tree.
  `error_boundary()` now also logs exactly one `command.failed` line per caught
  failure, and each dispatched shell line binds its own correlation id.
- **The API** — per `apps/api/README.md`/`CONTEXT.md`, the fixed Router → Mapper →
  Handler → Presenter pipeline, eager lifespan-time `Container` composition against
  `trutina-storage-postgres`, and the shared exception-handling seam are all live,
  non-scaffold code for `account`/`journal`/`posting`, with `system` as a documented
  flat exception. `apps/api/README.md` now exists (resolving the prior "no README"
  gap), but it does not enumerate test-tier coverage per feature the way
  `apps/cli`'s documentation does — whether all three features have all five test
  tiers written remains unconfirmed in this pass. `create_app()` now configures
  logging and attaches `CorrelationIdMiddleware`; every exception handler logs
  exactly one `request.failed` line through a shared `_log_failure()` helper.
- **Trial balance** — `TrialBalanceService`, `TrialBalanceRepo`, `AccountBalanceEntry`,
  and `TrialBalanceViewModel` in `trutina-core`; `PostgresTrialBalanceRepo` in
  `trutina-storage-postgres` (a `GROUP BY` over `postings`, no migration); the
  `trial-balance` CLI command; and `GET /trial-balance`. All four layers have unit and
  integration tests. All-time or single `as_of_date` cutoff only; accounts without
  postings do not appear; PostgreSQL only. `TrialBalanceService` now also logs
  `trial_balance.generated` (entry count and `as_of_date` only — never an amount)
  on every successful report.

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
  optional `has_postings` callback. Both `apps/api`'s `build_container()` and
  `apps/cli`'s `CliContext` now supply it against the posting repository —
  confirm coverage with tests before treating this item as fully closed.
- No test yet forces a real Postgres constraint violation and inspects the
  resulting exception's text for a leaked value — `hide_parameters=True` is
  confirmed set on the engine, but this specific masking behavior is not yet
  directly exercised by a test.
- Identity and authentication — `trutina-authentication` provides contracts and test
  fakes only. No password hasher, token implementation, storage adapter, route or
  command exists, no `AUTH_*` `ErrorCode` exists, and no app depends on the package.
  The token, refresh-token and login-attempt contracts are provisional.
  Separately from that package, `trutina-core`'s journal and posting write services now require a non-blank `actor: str` and discard it after the check; it is not persisted yet.

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
3. **Withdrawn — was previously flagged as a confirmed syntax defect.**
   `except KeyError, IndexError:` in `api/shared/errors/handlers.py::_fill()` was
   flagged in earlier passes of this document (and of `ROADMAP.md`, `AGENTS.md`,
   `ARCHITECTURE.md`, `apps/api/CONTEXT.md`) as invalid Python 3 syntax. Confirmed
   during the logging rollout's Phase 3 that this is in fact valid PEP 758 syntax
   on Python 3.14 (the unparenthesized multi-exception form is permitted when
   there is no `as` clause) — the file imports and runs cleanly, `ruff format`
   with `target-version = "py314"` does not rewrite it, and CI has never failed
   on it. This flag is now closed and removed from every document that
   previously carried it.
4. **Root import-linter storage-layer naming — resolved in a prior pass,
   re-confirmed here.** The root `pyproject.toml`'s `layers` contract names its
   storage-adjacent layer as `"trutina.storage_mongo | trutina.storage_postgres |
trutina.observability"` — all three sit at the same position, with
   `trutina.observability` added during the logging rollout. `ARCHITECTURE.md`
   and `AGENTS.md` both reflect this current three-member layer.
5. **Root compose files and PostgreSQL — resolved in M0a-C (#43).** `compose.yml`
   provisions PostgreSQL, a one-shot `migrate` service, and the API, and
   `compose.dev.yml` watches every package the API image runs, including
   `trutina-observability`. `tools/docker-smoke.sh` was run end to end and passes,
   including its structured-logging assertion.
6. **A real, since-fixed bug found during the logging rollout's own
   verification, recorded here for cross-package visibility.** Alembic's
   generated `env.py` (for `trutina-storage-postgres`'s migrations) calls
   `logging.config.fileConfig()` against `alembic.ini`'s `[loggers]` section,
   which names only `root`/`sqlalchemy`/`alembic`. `fileConfig()` defaults to
   `disable_existing_loggers=True`, which silently disabled every other
   already-instantiated Python logger in the process for the rest of a test
   session — including this workspace's own
   `trutina.storage_postgres.shared.connection` logger, whose `db.connected`/
   `db.disconnected` log lines became silent no-ops after the first migration
   ran. Fixed by passing `disable_existing_loggers=False` explicitly in `env.py`,
   plus a belt-and-braces re-enable step added to `tests/fixtures/postgres.py`'s
   `schema_init`. See `packages/storage-postgres/CONTEXT.md` for the full
   account; this entry exists so the fact is discoverable from this
   cross-package document too, not only from that package's own docs.

## Testing Strategy (cross-cutting)

Every package/app's tests are collected from one root `pytest.ini`
(`testpaths = tests apps packages`), with a mandatory three-axis marker
discipline enforced by root `conftest.py`: a hand-written speed marker
(`unit`/`integration`), an automatically-derived layer marker
(`core`/`infra`/`cli`/`api`/`shared`/`config`/`observability`/`authentication`, derived from file
path — never hand-written), and, for `infra`-layer tests only, an
automatically-derived backend marker (`mongo`/`postgres`, derived from which
storage package's directory the test lives under). This lets
`pytest -m "unit and cli"` or `pytest -m "integration and infra and postgres"`
remain trustworthy filters instead of decorative metadata that could silently
drift from where a test actually lives. Root `tests/` holds only shared
fixtures/factories/fakes; every package/app's real test cases live beside its own
code. `tests/fixtures/postgres.py`'s session-scoped `schema_init` applies the
real Alembic migration history once per session and re-enables every logger
afterward (see Cross-Package Conflict #6 above). `tests/fixtures/logging.py`'s
autouse fixture removes only the handler `trutina-observability`'s
`configure_logging()` installed itself, after every test.

## Long-Term Direction

- Confirm and, if needed, correct the `default_posting_date()` conflict above.
- Confirm `apps/api/README.md`'s test-tier coverage feature-by-feature, the way
  `apps/cli/README.md` already does for the CLI.
- Extend reporting beyond the trial balance (full-chart output, period ranges,
  financial statements).
- Add import/export and external integration surfaces once reporting exists.
- Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status
  directly against current `trutina-core` source.
- Add a test exercising `hide_parameters=True`'s actual masking effect against a
  real Postgres constraint-violation exception's text, not just confirming the
  flag is set on the engine.
- Build identity and authentication on the `trutina-authentication` contracts, in
  the milestone order recorded in the identity and authentication plan.
