# Trutina Roadmap

## Purpose

This roadmap lists work that the confirmed package/app passes (`packages/shared`,
`packages/config`, `packages/core`, `packages/storage-mongo`, `packages/storage-postgres`,
`apps/api`, `apps/cli`) show is **genuinely still missing or unresolved** — not a
restatement of any package's internal extension points, which live in that package's
own README/CONTEXT.

## Roadmap Principles

- Do not mark an item complete unless a package's own, independently-verified
  README.md/CONTEXT.md confirms the code exists and is coherent with its
  surrounding modules.
- Keep accounting correctness ahead of new presentation surfaces or reporting.
- Resolve cross-package documentation conflicts before building on top of the
  areas they touch.

## Immediate — Documentation Debt

- **Resolve the `default_posting_date()` conflict.** `trutina-shared` documents
  it as unused; `apps/cli`'s journal parser calls it. Check
  `packages/shared/src/trutina/shared/util.py` and
  `apps/cli/src/trutina/cli/features/journal/parser.py` directly and correct
  whichever doc is stale. Not re-confirmed against live source in this pass.
- **Fix the confirmed `except KeyError, IndexError:` syntax defect** in
  `api/shared/errors/handlers.py`. `apps/api/CONTEXT.md` now confirms this against
  live source as a real, invalid-Python defect — this is no longer an open question
  of whether it's a bug, only of when it gets fixed.
- **Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold
  status** against current `trutina-core` source — carried forward from prior
  docs without independent re-verification in this pass.
- **Provision PostgreSQL in root `compose.yml`/`compose.dev.yml`.** Both files
  currently wire up only MongoDB (env vars, service, volume-sync targets), even
  though `apps/api` and `apps/cli` both declare `trutina-storage-postgres` as their
  storage dependency in their own `pyproject.toml`. Confirmed stale in this pass.

## Remaining Domain / Reporting Work

- Add storage-level uniqueness enforcement where still needed beyond what
  `trutina-storage-postgres`'s unique/foreign-key constraints already provide.
- Add trial balance calculation, account balance summaries, and historical
  report views — no reporting pipeline exists in `trutina-core` today.
- Add future financial statement support once trial balance exists.

## Remaining Infrastructure Work

- Add multi-document transaction support to `MongoPostingRepo.save_many()` — the
  current single `insert_many()` call has no `ClientSession`, so a mid-batch
  failure can partially persist a journal's postings, and concurrent posting
  attempts can race past `PostingService`'s existence pre-check. Documented as
  an accepted, not yet closed, gap in `trutina-storage-mongo`'s own CONTEXT.md.
  This no longer blocks anything app-facing, since neither presentation app
  depends on `trutina-storage-mongo`.
- Wire the `ACCOUNT_HAS_POSTINGS` delete safeguard for `trutina-storage-postgres`
  — `AccountService.delete_account()` only enforces it when a composition root
  supplies the optional `has_postings` callback; confirm whether either app's
  composition currently supplies it.
- Close the connection-level timeout-vs-unavailable error split in
  `trutina-storage-postgres`'s `connect()`.

## Remaining Presentation Work

- **API:** `apps/api/README.md` now exists, resolving the prior "no README"
  gap. It does not yet enumerate test-tier coverage per feature the way
  `apps/cli`'s documentation does — whether `account`/`journal`/`posting` each
  have all five tiers (mapper/presenter/handler/router-unit/router-integration)
  actually written remains unconfirmed in this pass.
- **CLI:** per `apps/cli/README.md`/`CONTEXT.md`, future CLI work is limited to
  new command groups once a reporting pipeline exists, plus any further
  shell-completion or interactive-workflow enhancements — no other CLI gaps were
  identified in this pass.

## Remaining Integration Surfaces

- Add CSV or structured import/export.
- Add machine-readable output formats.
- Add other external integration surfaces (none exist today in any package).

## Success Criteria

Trutina should be considered on track when, in addition to what is already true
today (balanced-entry enforcement, deterministic journal numbering and posting
derivation, stable repository contracts, storage isolated behind interfaces, a
shared error-rendering boundary in both presentation apps, a completed
Postgres cutover for both `apps/cli` and `apps/api`):

- the `default_posting_date()` documentation conflict is resolved with a
  source-level check, not a guess;
- the confirmed `handlers.py` syntax defect is fixed, not just documented;
- root `compose.yml`/`compose.dev.yml` provision PostgreSQL for local
  development, matching what `apps/api`/`apps/cli` actually depend on;
- `apps/api/README.md`'s test-tier coverage is confirmed feature-by-feature the
  way `apps/cli/README.md` already is;
- trial balance reporting is available from validated account/journal/posting
  data;
- `MongoPostingRepo.save_many()`'s transaction gap is closed or explicitly
  re-accepted with a documented reason;
- future features continue to leave `trutina.core` free of `beanie`/`pymongo`
  and `sqlalchemy`/`asyncpg` imports, and free of CLI/API awareness.
