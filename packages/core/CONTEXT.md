# trutina-core — Context

For usage, see README.md. This document explains why, not how.

Audience: maintainers, reviewers, and future contributors deciding whether a change
belongs in this package and whether it preserves the guarantees the rest of the
monorepo depends on.

## Why This Package Exists Separately

The accounting domain (validation rules, service workflows, repository contracts)
used to live inside a single application package alongside the CLI. As the project
grew into `apps/cli` and `apps/api` — two presentation layers needing identical
business logic — that coupling would have forced either duplicated domain code or a
CLI-shaped dependency inside the API. Extracting `trutina-core` as its own workspace
package removes that choice: both apps depend on the same domain package, and neither
can accidentally depend on the other's presentation concerns.

This is also what makes the domain layer fast to test. A `JournalService` test
substitutes a `Fake*Repo` and runs in-process with no I/O; that would not be possible
if the service were entangled with Mongo document classes or Typer command objects.

## Layering: What's Allowed, What's Forbidden

Enforced mechanically by `import-linter` at the workspace root
(`pyproject.toml`'s `[[tool.importlinter.contracts]]`), not just by convention:

```text
apps.cli | apps.api
        ▼
trutina.storage_mongo | trutina.storage_postgres | trutina.observability
        ▼
trutina.core            ← this package
        ▼
trutina.shared | trutina.config
```

Three contracts apply directly to this package:

1. **`trutina.core` may not import `beanie` or `pymongo`**, at all, anywhere. This
   is checked as a `forbidden` contract, not a `layers` contract — it's stronger than
   "core is above infrastructure," it's "core has zero awareness that Mongo exists."
   A repository contract (`AccountRepo`, `JournalRepo`, `PostingRepo`) is defined
   entirely in terms of domain types; nothing about its shape may leak a storage
   detail.
2. **`trutina.core` may not import `sqlalchemy` or `asyncpg`**, at all, anywhere —
   the same rule, applied to the second storage backend once it existed.
3. **Internal ordering: `posting → journal → account`**, one-directional. `posting`
   may import from `journal` and `account`; `journal` may import from `account`;
   `account` may import from neither. This mirrors the real dependency in the
   accounting model — a posting is derived from a journal entry, which references
   accounts — and is enforced as its own `layers` contract so a future edit can't
   quietly introduce a cycle (e.g. `account` importing something from `posting` to
   support a "show postings for this account" convenience method — that capability
   belongs in a service that depends on both, not inside `account` itself).

The layering rules are what let `AccountService`, `JournalService`, and
`PostingService` be trusted in isolation. If `account/` could reach into `posting/`,
a bug fix in one module could silently change behavior in a module that has no test
coverage for that interaction. The one-directional rule keeps the blast radius of any
change legible from the import statements alone.

A fourth workspace-level rule applies here too, though it has no dedicated
`forbidden` contract of its own the way the two storage bans do: this package emits
through `logging.getLogger(__name__)` exclusively, never through `structlog` or
`trutina.observability`. This is covered by the "Emitters use stdlib logging only"
contract, which names `trutina.core` explicitly among its `source_modules`. See
"Why Services Log Success, Never Failure" below for what that means in practice.

`trutina.core.trial_balance` sits outside the `posting → journal → account` contract.
It imports only from `trutina.shared`, and no import-linter contract names it, so its
independence from `posting` is a property of the current source, not an enforced rule.

## Design Decisions and Why They Were Made

### Repository contracts live in core; implementations do not

`AccountRepo`, `JournalRepo`, and `PostingRepo` are abstract (`abc.ABC`) classes
defined here. Concrete adapters (`MongoAccountRepo`, `PostgresAccountRepo`, etc.) live
in the two storage packages — separate, lower-level-of-abstraction-but-higher-in-the-
dependency-graph packages. This is the Dependency Inversion Principle applied
literally: the domain defines the contract; storage conforms to it, not the other
way around.

Trade-off accepted: core cannot express storage-specific concerns (transactions,
indexes, connection pooling) anywhere in its own types. `PostingRepo.save_many()`
does not promise all-or-nothing persistence, so any stronger adapter guarantee must
be documented and tested by that adapter. This is deliberate: the alternative
(leaking a `session` parameter or similar into the contract) would violate the
zero-storage-awareness rule for a marginal gain.

### DTOs and ViewModels, not raw domain models, at the service boundary

Every service method accepts a DTO (`CreateAccountInput`, `CreateJournalInput`) and
returns a ViewModel (`AccountViewModel`, `JournalViewModel`, `PostingViewModel`)
rather than the underlying Pydantic domain schema (`Account`, `JournalEntry`,
`LedgerPosting`). This is intentional redundancy, not an oversight: it lets the
domain schema evolve (add a private field, change an internal computed property)
without changing what every caller — CLI formatters, API response models — has to
depend on. It also gives DTOs room to have their own validation semantics that don't
belong on the domain model. `UpdateAccountInput`'s `None`/omitted/explicitly-provided
distinction for partial updates is a DTO-only concept; `Account` itself has no notion
of a partial update.

Trade-off accepted: every service method has a mapping step (`_to_view_model`,
`_to_entry_view`). This is boilerplate, but it's boilerplate in exactly one place per
feature (the service), not duplicated across every consumer.

### `LedgerPosting` is frozen; there is no posting input DTO

Postings are a derived, historical record — once a journal entry is posted, that
posting is the ledger's permanent record of the event. Making `LedgerPosting`
Pydantic-frozen (`ConfigDict(frozen=True)`) enforces that at the type level: nothing
in the codebase can mutate a posting after construction, including future code that
hasn't been written yet.

The absence of a posting input DTO is the same decision from the other direction:
there is no legitimate caller-supplied posting, because a posting only ever comes
from `PostingService` deriving it from an already-persisted `JournalViewModel`. Add
one only if a future feature genuinely needs to accept an externally-supplied
posting (e.g. an import/migration tool) — and if that happens, it should probably be
a distinct workflow, not a widened `PostingService.post_journal_entry`.

### Normal balance is computed, never stored

`Account.normal_balance` is a `computed_field`, derived from `category` via a static
lookup table (`NORMAL_BALANCE_BY_CATEGORY`), not a persisted field. Storing it
independently would allow a category and its balance side to disagree after an edit
— e.g. an account changed from `ASSET` to `REVENUE` without its stored
`normal_balance` being updated in the same write. Deriving it removes that failure
mode entirely rather than requiring service-layer discipline to prevent it.

The same reasoning applies to `JournalEntry.total_debits`, `total_credits`,
`is_balanced`, and `PostingViewModel.is_debit` — anywhere a value is fully
determined by other fields on the same model, it is derived, not stored. Note that
`LedgerPosting.is_debit` is a plain `@property` rather than a Pydantic
`computed_field` (unlike `PostingViewModel.is_debit`, which is a real
`computed_field`) — both achieve the same "never stored, always derived" guarantee,
just via different mechanisms at the domain-schema layer versus the DTO layer.

### Trial balance is a read model over postings, with no peer-service dependency

`TrialBalanceService` produces a report from persisted `LedgerPosting` data and writes
nothing, so `TrialBalanceRepo` has a single read method,
`get_account_balances(as_of_date=None)`. The repository returns one
`AccountBalanceEntry` per account with at least one posting in scope, ordered by
account name, and an empty list when nothing is in scope.

The aggregation (summing debits and credits per account) lives in the repository
because it is the query. Report-level figures live in the service's output:
`TrialBalanceViewModel.total_debits`, `total_credits`, and `is_balanced` are computed
from `entries`, never stored, so they cannot disagree with the rows they summarize.
`is_balanced` reports whether the books balanced; it does not enforce it. Every
`JournalEntry` already validated its own balance at creation, so a `False` result would
mean corrupted or partially migrated data.

The service holds only its repository. Everything it reads was validated when the
postings were created, so it neither calls `JournalService`/`AccountService` nor
re-checks amounts or account existence. Only posted entries count: an unposted
`JournalEntry` has no postings and contributes nothing.

`AccountBalanceEntry` is frozen and, unlike `LedgerPosting`, is not single-sided: an
account's history legitimately contains both debit and credit postings, so both totals
are independently non-negative and are not netted. There is no input DTO, because a
trial balance is computed, never submitted.

`as_of_date` is not validated. Any value is accepted: a future date includes every
posting, and a date before the earliest posting yields an empty report.

### Validation lives in the domain schema, not the service

`JournalEntry`'s balance check, `JournalLine`'s debit/credit exclusivity, and
`Account`'s name normalization are all Pydantic validators on the schema itself, not
checks written imperatively in the service. A service that wants to enforce a rule
constructs the domain object and lets construction fail — it does not duplicate the
rule as an `if` statement first.

This guarantees the invariant holds for _every_ construction path, not just the one
the current service method happens to use. If a second service, or a test factory,
or a future migration script constructs a `JournalEntry` directly, the balance rule
still applies — there is no way to build an invalid one by going around the service.

Exception, and why it's not actually an exception: `JournalService` checks account
existence (`_validate_accounts`) before constructing the domain entry. This is not
domain validation moved into the service — it's a cross-aggregate check (does this
journal line's account exist in the chart?) that the `JournalLine` schema has no way
to answer on its own, since it has no repository access and no knowledge of any
chart snapshot. Cross-aggregate checks belong in the service; single-aggregate
invariants belong in the schema. This is the dividing line to preserve when adding a
new validation rule — ask whether the check needs data outside the object being
constructed.

### Write methods take an opaque actor, checked for presence only

**Decision:** `JournalService.create_journal_entry` and
`PostingService.post_journal_entry` take a required keyword-only `actor: str`.
Each calls `is_non_blank_actor` from `trutina-shared` as its first statement and
raises `ValidationAppError.required_field("actor", actor)` when it is blank.

**Why:** a write that cannot be attributed to a caller cannot be audited later.
A required parameter turns a forgotten actor into a type error, and checking it
first means a rejected call performs no repository or chart access and consumes
no journal number. Core sees only an opaque string: it never imports
`trutina.authentication`, and no service method takes an `Identity`. The format
(UUID, `system:` prefix) is the calling application's concern.

**Current behavior:** the actor is validated and then dropped. It is not
persisted and not added to any log context.

### `AppError` / `ValidationAppError` are the only exceptions crossing the service boundary

Every `raise` inside a service is one of these two types (from `trutina-shared`),
or a `pydantic.ValidationError` caught and translated into one before it escapes.
This is what lets every consumer — CLI's `error_boundary()`, the API's exception
handlers — write exactly one catch clause per error type and be confident nothing
else can leak through. A service method that lets a raw `KeyError` or a
storage-driver exception escape is a bug in that service, not a caller's problem to
work around.

### Why Services Log Success, Never Failure

**Decision:** Each of the four services emits exactly one `logging.INFO` line
through `logging.getLogger(__name__)` after a state-changing write actually
succeeds — never before, never speculatively, and never on any path that raises
`AppError`/`ValidationAppError`. Read-only methods (`get_*`, `list_*`,
`resolve_*`) never log anything.

**Why success-only:** a failure is already fully described by the `AppError`/
`ValidationAppError` that propagates out of the service — `.code`, `.context`,
and (for infra failures) `.cause` are all a caller needs to log it correctly, and
exactly one seam (an API exception handler, the CLI's `error_boundary()`) is
responsible for turning that into exactly one log line, at the right level, with
the right traceback policy. If the service _also_ logged on its own failure path,
one real failure would produce two log lines — one from the service, one from the
seam — undermining the "log where the error is handled, not where it is raised"
principle the whole workspace's logging design follows. Success events have no
such duplicate-logger problem, since nothing downstream re-announces "this
succeeded" — the service is the only place that knows the write actually landed.

**Why no monetary field is ever logged:** `journal.created` and `posting.created`
log `journal_number`/`line_count`, never a debit or credit amount;
`trial_balance.generated` logs `entry_count`/`as_of_date`, never a balance. This is
enforced as policy here (nothing in `trutina.core` computes a totals-bearing log
line), and independently backstopped by `trutina-observability`'s redaction
processor, which drops any key matching a known monetary name above `DEBUG` — but
the primary control is simply never emitting the value from the source in the
first place.

**Why this module only imports `logging`, never `trutina.observability` or
`structlog`:** the same reasoning that keeps `beanie`/`pymongo`/`sqlalchemy`/
`asyncpg` out of this package applies here — `trutina-core` must remain usable,
testable, and importable with zero knowledge of how or where its log lines end up
formatted or routed. Any application composing this package's services decides
that, once, at its own composition root; this package only ever decides _that_
something happened.

## Control Flow and Data Flow

A representative request, posting a journal entry to the ledger, illustrates the
cross-service shape that recurs throughout core:

```text
PostingService.post_journal_entry(journal_number)
    │
    ├─▶ is_non_blank_actor(actor)                           (ValidationAppError if blank)
    │
    ├─▶ JournalService.get_journal_entry(journal_number)   (fetch, not construct)
    │       └─▶ JournalRepo.get_by_number(...)
    │
    ├─▶ PostingRepo.get_by_journal_number(...)              (duplicate-post guard)
    │
    ├─▶ [derive one LedgerPosting per JournalLine]            (pure, in-process)
    │
    ├─▶ PostingRepo.save_many(postings)                      (one repository batch)
    │
    └─▶ logger.info("posting.created", ...)                  (only after save succeeds)
```

```text
TrialBalanceService.get_trial_balance(as_of_date=None)
    │
    ├─▶ TrialBalanceRepo.get_account_balances(as_of_date)   (one aggregation)
    │
    ├─▶ TrialBalanceViewModel(entries, as_of_date)           (totals derived, not stored)
    │
    └─▶ logger.info("trial_balance.generated", ...)          (entry_count, as_of_date only)
```

Services call other services (`PostingService` holds a `JournalService`;
`JournalService` holds an `AccountService`), never reaching down to a repository they
don't own. `PostingService` never touches `AccountRepo` or `JournalRepo` directly —
it only ever sees `JournalViewModel`, already fully validated, from `JournalService`.
Concretely, `PostingService` performs zero re-validation of journal line amounts or
account existence, because those are `JournalEntry`/`JournalLine` invariants already
enforced upstream, and re-checking them here would be exactly the kind of duplicated-
rule drift the domain-validation design decision above exists to prevent.

## Assumptions This Package Relies On

- Every constructed domain object is immediately valid or immediately rejected.
  There is no notion of a "draft" or partially-valid `Account`/`JournalEntry`
  anywhere in core. If a future feature needs staged/draft entries, that is a new
  concept requiring new design, not an extension of the existing schemas.
- A `ChartOfAccounts` snapshot is a point-in-time view, not a live handle.
  `AccountService.get_chart()` is documented as something callers validating
  multiple references must call once and reuse — calling `resolve_account()` in a
  loop instead rebuilds the chart from `repo.list_all()` on every call, and two such
  calls are not guaranteed to observe the same data. This is a real race window under
  concurrent writes; it is accepted because closing it fully would require
  transactional snapshot reads the current repository contract doesn't provide.
- Repository method contracts (return `None` on a miss and translate storage
  failures to `AppError`) are promises, not enforced by core. Treat every repository
  contract docstring in `repo.py` as a spec an adapter must satisfy, and check that
  any new adapter's tests actually assert the documented behavior, not just
  typical-path success.

## Known Gaps

- `AccountService.create_account()`/`update_account()` perform their duplicate-code
  and duplicate-name checks as a pre-check (`exists_by_code`/`exists_by_name`)
  before construction and persistence — this is not atomic with the subsequent
  `create`/`update` call. Under concurrent writes, two callers can both pass the
  pre-check before either persists; the storage-layer unique index is the actual
  authority in that case, and the adapter is expected to translate the resulting
  conflict into `AppError.conflict()`. This is a deliberately accepted TOCTOU
  window, not an oversight — closing it would require pushing transaction/session
  semantics into a contract that is supposed to stay storage-agnostic.
- `AccountService.delete_account()` enforces a posting-history safeguard only when
  its optional `has_postings` callback is supplied at composition time. Without that
  callback it performs an existence check and deletes the account, so compositions
  that omit the callback do not protect posting history. Both `apps/api`'s
  `build_container()` and `apps/cli`'s `CliContext` now supply it.
- `TrialBalanceService` lists only accounts with postings. Listing every chart account
  as zero rows would be a `TrialBalanceService`-level combination with
  `AccountService.list_accounts()`, not a `TrialBalanceRepo` change; it is not built.
- `TrialBalanceRepo` has a PostgreSQL implementation only.
- No `caplog` test yet asserts, across all four services in one pass, that every
  raised-`AppError` path leaves zero log records behind — each service's own test
  file covers this individually, but there is no single cross-service regression
  test pinning "core never logs on failure" as one assertion. Low risk (each
  service's own tests already cover it), tracked as a minor Phase 7 nice-to-have,
  not a blocker.
- The `actor` on `create_journal_entry` and `post_journal_entry` is validated for
  presence and not persisted. Repository contracts take no attribution, so no
  stored row records who wrote it.

## Common Mistakes to Avoid

- Constructing a domain schema directly from CLI/API code to "save a round trip."
  This bypasses whatever cross-aggregate check the service was performing (e.g.
  account-existence validation) and produces an object that may be structurally
  valid but business-invalid. Always go through the service.
- Adding a new cross-cutting validation as an `if` in a service method instead of a
  schema validator, when the check only needs data already on the object being
  constructed. If it doesn't need a repository or another service, it belongs on the
  schema.
- Introducing an import from `account` into `journal` or `posting` that goes the
  wrong direction, or any import of `beanie`/`pymongo`/`sqlalchemy`/`asyncpg`
  anywhere in this package. All are caught by CI's import-linter step, but catching
  it locally (`uv run lint-imports`) before pushing is faster than waiting on CI to
  reject it.
- Assuming `PostingService` re-validates what `JournalService` already validated. It
  doesn't, on purpose. If you find yourself wanting to add an amount or
  account-existence check inside `PostingService`, that's a signal the check belongs
  on `JournalEntry`/`JournalLine` instead, where it will also protect every other
  caller of `JournalService`.
- Treating `AppError.code` as optional to check. Catching bare `AppError` without
  inspecting `.code` in a caller that needs to distinguish "already posted" from
  "unknown journal number" will misbehave — both raise the same exception type.
- Adding a log call on a service's failure path "for visibility." The seam that
  catches the exception already owns exactly one log line for that failure — a
  second one here is a duplicate, not an enhancement. If a failure genuinely isn't
  visible enough at the seam, fix the seam's log line, not this package.
- Importing `trutina.observability` or `structlog` into a service "to get
  structured fields for free." Plain `logging.getLogger(__name__).info(event,
extra={"context": {...}})` is the full contract — the composing app's
  `configure_logging()` call is what turns that into structured output, not
  anything this package does.
- Giving a service method an `Identity`, or importing `trutina.authentication`,
  to "pass the user through." Core receives an opaque `actor: str` from its
  caller and checks only that it is non-blank.
