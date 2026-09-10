# Trutina Roadmap

## Purpose

This roadmap lists work that the six verified package/app passes (`packages/shared`,
`packages/config`, `packages/core`, `packages/infrastructure`, `apps/api`,
`apps/cli`) confirm is **genuinely still missing or unresolved** — not a
restatement of any package's internal extension points, which live in that
package's own README/CONTEXT.

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
  whichever doc is stale.
- **Write `apps/api/README.md`.** Every other package/app has a README pass;
  API maturity (which features have all five test tiers, current public routes)
  is currently only described in `apps/api/CONTEXT.md`.
- **Confirm or refute the `except KeyError, IndexError:` flag** in
  `api/shared/errors/handlers.py` against live source.
- **Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold
  status** against current `trutina-core` source — carried forward from prior
  docs without independent re-verification in this pass.

## Remaining Domain / Reporting Work

- Add storage-level uniqueness enforcement where still needed beyond what
  `trutina-storage-mongo`'s Mongo unique indexes already provide.
- Add trial balance calculation, account balance summaries, and historical
  report views — no reporting pipeline exists in `trutina-core` today.
- Add future financial statement support once trial balance exists.

## Remaining Infrastructure Work

- Add multi-document transaction support to `MongoPostingRepo.save_many()` — the
  current single `insert_many()` call has no `ClientSession`, so a mid-batch
  failure can partially persist a journal's postings, and concurrent posting
  attempts can race past `PostingService`'s existence pre-check. Documented as
  an accepted, not yet closed, gap in `trutina-storage-mongo`'s own CONTEXT.md.

## Remaining Presentation Work

- **API:** bring `apps/api` test-tier coverage (mapper/presenter/handler/
  router-unit/router-integration per feature) up to the same
  confirmed-complete standard the CLI's own docs already meet, and document it
  in a new `apps/api/README.md`.
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
shared error-rendering boundary in both presentation apps):

- the `default_posting_date()` and API-maturity documentation conflicts above are
  resolved with a source-level check, not a guess;
- `apps/api/README.md` exists and independently confirms API maturity the way
  `apps/cli/README.md` already does for the CLI;
- trial balance reporting is available from validated account/journal/posting
  data;
- `MongoPostingRepo.save_many()`'s transaction gap is closed or explicitly
  re-accepted with a documented reason;
- future features continue to leave `trutina.core` free of `beanie`/`pymongo`
  imports and free of CLI/API awareness.
