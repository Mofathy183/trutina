# Trutina Roadmap

## Purpose

This roadmap lists work that the confirmed package/app passes (`packages/shared`,
`packages/config`, `packages/core`, `packages/observability`,
`packages/storage-postgres`, `apps/api`, `apps/cli`) show is
**genuinely still missing or unresolved** — not a restatement of any package's
internal extension points, which live in that package's own README/CONTEXT.

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
- **Re-confirm `modules/journal/rule.py` / `modules/posting/rule.py` scaffold
  status** against current `trutina-core` source — carried forward from prior
  docs without independent re-verification in this pass.
- **Correct the `parse_as_of_date()` module docstring** in
  `apps/cli/.../features/trial_balance/parser.py`. It says date-range rules are
  enforced downstream by `LedgerPosting`/`AccountBalanceEntry`; no validation of
  `as_of_date` exists anywhere in the trial balance path.

## Remaining Domain / Reporting Work

- Add storage-level uniqueness enforcement where still needed beyond what
  `trutina-storage-postgres`'s unique/foreign-key constraints already provide.
- Extend the trial balance to list every account in the chart, including accounts
  with no postings, as zero rows. Today only accounts with at least one posting in
  scope appear. This is a `TrialBalanceService`-level join with
  `AccountService.list_accounts()` and does not change `TrialBalanceRepo`.
- Add reporting views that span more than a single as-of cutoff (period ranges,
  period-over-period comparison). The trial balance supports all-time or one cutoff
  date only.
- Add financial statement support on top of the trial balance.
- Add fiscal-period closing and multi-currency support. No code exists for either.

## Remaining Infrastructure Work

- Wire the `ACCOUNT_HAS_POSTINGS` delete safeguard for `trutina-storage-postgres`
  — `AccountService.delete_account()` only enforces it when a composition root
  supplies the optional `has_postings` callback. Both `apps/api`'s `build_container()`
  and `apps/cli`'s `CliContext` now supply it against the posting repository.
  Confirm coverage with tests before removing this item.
- Close the connection-level timeout-vs-unavailable error split in
  `trutina-storage-postgres`'s `connect()`.
- Evaluate a faster path for the trial balance if ledgers grow large. Each call runs
  one `GROUP BY` over the postings in scope, and `posting_date` has no dedicated
  index, so the `as_of_date` filter is not index-assisted.
- Add a test forcing a real Postgres constraint violation and asserting the
  resulting exception's text contains no leaked account code/name/amount —
  `hide_parameters=True` is confirmed _set_ on the engine, but its actual
  masking effect on a real exception's text is not yet directly exercised.

## Remaining Presentation Work

- **API:** `trial_balance` has all four test tiers written that apply to it
  (presenter, handler, mapper, router-unit, router-integration). Whether
  `account`/`journal`/`posting` each have every tier written remains unconfirmed
  in this pass, and `apps/api/README.md` does not enumerate them.
- **CLI:** `trial-balance` is a flat top-level command. `--as-of` resolves to
  midnight on the given date, so a posting stamped later on that same day is
  excluded. Decide whether the cutoff should mean end of day. Confirm that
  one-shot invocation (`trutina-cli trial-balance`) is dispatched by `main.py`
  rather than opening the shell. Further CLI work is new command groups and
  shell/interactive enhancements.
- **Windows file rotation** for the CLI's default log sink is not exercised at
  real volume — two CLI processes holding the same log file open simultaneously
  could, in principle, fail to rotate. Low risk at the current default (5 MB
  threshold), not yet observed as an actual problem.

## Remaining Integration Surfaces

- Add CSV or structured import/export.
- Add machine-readable output formats beyond the existing API JSON.
- Add other external integration surfaces (none exist today in any package).

## Identity and Authentication

`trutina-authentication` contains contracts and fakes and a concrete Argon2id `PasswordHasher`,
and its `UserRepo` and `LoginAttemptRepo` have PostgreSQL adapters (`users` and `login_attempts` tables). Still missing:

- Actor attribution: journal, posting and account writes validate a required `actor` and pass it to the repository as `created_by`.
  `trutina-storage-postgres` persists it as a column for journal entries and postings and as an `audit_events` row for account writes.
  Still missing: replacing the fixed pre-auth constants with real identities (M4b, M4.5).
- Password registration and login, with throttling. The hasher, user store and login-attempt store exist;
  email format validation, a password length limit and the throttling policy do not.
- Access and refresh tokens, auth routes, and endpoint protection.
- A CLI `auth` group.
- Authorization (roles and a permission matrix).
- Secret-safe validation errors (M2.1) are done for `FieldViolation.value`,
  the API 422 body and CLI rendering, proven with a test-only model. Still to do:
  re-verify on the real credential routes (M3.7). Credential detection is name-based and the marker list exists in two packages.

The milestone order, locked decisions and open question (JWT versus one opaque
session mechanism) are in the identity and authentication plan.

## Success Criteria

Trutina should be considered on track when, in addition to what is already true
today (balanced-entry enforcement, deterministic journal numbering and posting
derivation, stable repository contracts, storage isolated behind interfaces, a
shared error-rendering boundary in both presentation apps, a completed
Postgres cutover for both `apps/cli` and `apps/api`, a trial balance
available from posted ledger data through both `trutina-cli` and `trutina-api`,
and structured, correlated logging shipped across both presentation apps and
every service/storage layer beneath them):

- the `default_posting_date()` documentation conflict is resolved with a
  source-level check, not a guess;
- `apps/api/README.md`'s test-tier coverage is confirmed feature-by-feature the
  way `apps/cli/README.md` already is;
- the trial balance can list every chart account, not only accounts with activity;
- future features continue to leave `trutina.core` free of `sqlalchemy`/`asyncpg`,
  `structlog`/`trutina.observability` imports, and free of CLI/API awareness.
