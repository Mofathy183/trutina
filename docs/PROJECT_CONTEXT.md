# Trutina Project Context

## Overview

Trutina is a Python double-entry bookkeeping engine. The repository is a `uv`
workspace, not a single application: `trutina-core` owns the accounting domain,
`trutina-storage-mongo` implements MongoDB persistence for it,
`trutina-config`/`trutina-shared` provide cross-cutting settings and error/validation
primitives, and two independent presentation apps — `trutina-cli` (Typer/Rich
terminal + interactive shell) and `trutina-api` (FastAPI) — sit on top of the same
domain services. This document explains why the workspace is shaped this way and
rolls up what each package's own, independently-verified `README.md`/`CONTEXT.md`
confirms is actually implemented today. For any package's internal reasoning, see
that package's own `CONTEXT.md` — this file does not restate it.

## Why Split Into a Workspace At All

Two presentation layers (`trutina-cli`, `trutina-api`) need identical business
rules. Keeping the domain in a separate, installable package (`trutina-core`) with
zero storage/transport awareness — rather than folding it into whichever app was
written first — means neither app can accidentally depend on the other's
presentation concerns, and the domain layer never needs to know either exists.
`trutina-storage-mongo` exists as its own package for the same reason: it is the
only place in the workspace allowed to import `beanie`/`pymongo`, so a repository
contract's storage-agnosticism is provable by import-linter, not just asserted by
convention. `trutina-shared` and `trutina-config` sit at the bottom because their
contents (validation rules, the error model, environment-driven settings) are
needed identically by every package above them and have no accounting-specific or
transport-specific shape of their own.

## What Is Genuinely Implemented End-to-End Today

- **Account, journal, and posting domains** — validated schemas, DTOs/ViewModels,
  and all three services (`AccountService`, `JournalService`, `PostingService`)
  are confirmed complete in `trutina-core`'s own README/CONTEXT, not partial.
- **MongoDB persistence** — concrete `MongoAccountRepo`, `MongoJournalRepo`,
  `MongoPostingRepo` implementations, connection lifecycle, and error translation
  are confirmed implemented and tested in `trutina-storage-mongo`.
- **The CLI** — `account`, `journal`, `posting` Typer command groups are fully
  wired end to end (command → parser/prompt → handler → service → repository),
  with unit and integration test tiers per feature, plus a working interactive
  shell with live tab completion derived from the real Click command tree.
- **The API** — per `apps/api/CONTEXT.md`, the fixed Router → Mapper → Handler →
  Presenter pipeline, composition (`Container`, eager lifespan-time construction),
  and the shared exception-handling seam are all described as live, non-scaffold
  code for `account`/`journal`/`posting`, with `system` as a documented flat
  exception. This pass could not independently confirm API test-tier coverage the
  way the CLI's own README/CONTEXT does, because no `apps/api/README.md` exists —
  flagged below.

## What Is Partial or Explicitly Out of Scope

- Trial balance, reporting, and historical views — not implemented anywhere in the
  workspace; no package's docs claim otherwise.
- Import/export or external integration surfaces — not implemented.
- `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status — carried
  forward from prior documentation but **not re-confirmed** against
  `trutina-core`'s current README/CONTEXT in this pass; treat as unconfirmed, not
  as verified fact, until checked directly against source.
- `MongoPostingRepo.save_many()` has no multi-document transaction — an accepted,
  documented gap in `trutina-storage-mongo`'s own CONTEXT.md, not an oversight
  discovered here.
- `get_field_violations()` (in `trutina-shared`) downgrades every domain-raised
  `ErrorCode` to `UNKNOWN_ERROR` on `FieldViolation.code`; the real code survives
  only as a string in `FieldViolation.value`. Both `trutina-cli` and `trutina-api`
  document their own recovery logic for this at the presentation layer — this is a
  known, accepted upstream gap, not independently re-fixed by either app.

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
2. **API test-tier maturity is asymmetric with the CLI's.** `apps/cli`'s own
   docs explicitly enumerate unit vs. integration test files per feature.
   `apps/api/CONTEXT.md` describes the same five-tier shape in the abstract
   (mapper/presenter/handler/router-unit/router-integration) and references
   existing shared fixtures (`fake_container`, `api_client`, `real_api_client`),
   but no `apps/api/README.md` exists to confirm, feature by feature, that all
   three (`account`/`journal`/`posting`) actually have all five tiers written
   today, the way the CLI's docs do. Treat API test coverage as "designed for"
   rather than "confirmed complete" until an `apps/api/README.md` pass exists.
3. **Possible syntax defect flagged, not confirmed.** `apps/api/CONTEXT.md`
   itself flags that `_fill()` in `api/shared/errors/handlers.py` appears to use
   `except KeyError, IndexError:`, which is invalid Python 3 syntax
   (`except (KeyError, IndexError):` is required). That pass could not confirm
   whether this is a live bug or an artifact of how the source was captured.
   Carried forward here as an open item, not silently dropped.

## Testing Strategy (cross-cutting)

Every package/app's tests are collected from one root `pytest.ini`
(`testpaths = tests apps packages`), with a mandatory two-axis marker discipline
enforced by root `conftest.py`: a hand-written speed marker (`unit`/`integration`)
plus an automatically-derived layer marker (`core`/`infra`/`cli`/`api`/`shared`,
derived from file path — never hand-written). This lets `pytest -m "unit and cli"`
or `pytest -m "integration and infra"` remain trustworthy filters instead of
decorative metadata that could silently drift from where a test actually lives.
Root `tests/` holds only shared fixtures/factories/fakes; every package/app's real
test cases live beside its own code.

## Long-Term Direction

- Confirm and, if needed, correct the `default_posting_date()` conflict above.
- Produce `apps/api/README.md` so API maturity can be confirmed the same way CLI
  maturity already is, rather than inferred from `CONTEXT.md` alone.
- Build trial balance and reporting support on top of the now-stable
  account/journal/posting domain.
- Add import/export and external integration surfaces once reporting exists.
- Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold status
  directly against current `trutina-core` source.
