# trutina-infrastructure — Architectural Context

This document explains why `trutina-infrastructure` is shaped the way it
is. For how to use it, see `README.md`. Nothing here should be duplicated
there.

## Why this architecture

`trutina-core` defines `AccountRepo`, `JournalRepo`, and `PostingRepo` as
abstract contracts with zero MongoDB or Beanie awareness. This package
exists to implement those contracts against a real database, so that the
accounting domain can be tested, read, and reasoned about without a
database running, and so a second storage backend could later be added by
satisfying the same three ABCs with no change to any service or domain
model.

Every repository method routes its Beanie call through
`MongoExecutor.run(coro)`, which wraps the call in
`translate_mongo_errors()`. This gives storage-specific concerns — today,
exception translation; potentially logging, metrics, retries, or
transaction coordination later — exactly one place to be added, instead of
requiring every repository method to be revisited individually. This is
stated as explicit design intent in `MongoExecutor`'s own docstring, not
an incidental convenience.

Each adapter defines exactly one `_to_document()` and one `_to_domain()`
static method, and every field written to or read from MongoDB passes
through that single boundary. This is what makes it tractable to reason
about serialization correctness (e.g. Decimal encoding) by reading one
method instead of auditing every call site that touches Mongo.
`_to_domain()` always constructs a real domain object
(`Account(...)`, `JournalEntry(...)`, `LedgerPosting(...)`), never a
bypassed `model_construct`-style shortcut, so every invariant the domain
model enforces is re-checked on every read, not just on write — storage
corruption or a bad migration surfaces as a validation error at read time
instead of silently propagating into the accounting workflow.

## Trade-offs accepted

**No multi-document transactions.** `MongoPostingRepo.save_many()` uses a
single `insert_many()` call with no `ClientSession`. This was accepted
because no transaction infrastructure exists anywhere in the workspace
yet, and adding one for a single call site would be premature. The cost is
a documented, accepted gap: a mid-batch interruption can partially persist
a journal's postings, and a concurrent posting attempt can race past
`PostingService`'s existence pre-check before either write lands — the
same category of TOCTOU window already accepted in
`AccountService.create_account()`.

**Two round-trips on account update.** `MongoAccountRepo.update()` loads
the existing document (to preserve `_id` and `created_at`) before calling
`replace()`. A single upsert-style call would be cheaper, but
`Document.save()` performs an upsert, which risks silently recreating a
deleted account. `replace()` without upsert, plus the extra read, was
chosen to keep "update a missing account raises `UNKNOWN_ACCOUNT`" a
guaranteed contract rather than an accidental one.

**Amounts stored as decimal strings, not BSON `Decimal128`.** Beanie's
default codec has no readily available lossless native decimal type for
this use case, so every monetary field (`JournalLineSubDocument`,
`PostingDocument`) is encoded as a string and decoded with `Decimal(value)`
on read. This trades index-friendliness and range-query ergonomics (a
future trial-balance query over amounts would need to decode first) for a
simpler, precision-guaranteed encoding today. Changing this later requires
a data migration, not just a code change.

**`journal_number` allocation bypasses Beanie.** `next_journal_number()`
talks to a raw, non-Beanie-registered `counters` collection via the
underlying Motor API directly, using `translate_mongo_errors()` standalone
rather than through `MongoExecutor`. This was necessary because Beanie has
no built-in primitive for atomic counter increments — it is the one place
in this package that deliberately steps outside the executor pattern, and
that exception is documented at the call site.

## How `DuplicateKeyError` is actually handled

`translate_mongo_errors()` catches `DuplicateKeyError` explicitly and
re-raises it unchanged, _before_ its generic `except PyMongoError` clause
that maps everything else to `AppError.unknown()`. Because that specific
clause is checked first, `DuplicateKeyError` always propagates out of
`MongoExecutor.run()` unchanged — nothing about the write path silently
collapses a uniqueness violation into `AppError.unknown()`.

What each write method (`MongoAccountRepo.create()`/`update()`,
`MongoJournalRepo.save()`) is responsible for is catching that re-raised
`DuplicateKeyError` at its own call site and delegating to a
per-repository `_on_duplicate()` method, which inspects the violated index
name (`violated_index()`) to decide which domain conflict to raise
(`DUPLICATE_ACCOUNT_CODE`, `DUPLICATE_JOURNAL_NUMBER`, etc.). If a write
method omitted that outer `except DuplicateKeyError` clause, the real
failure mode is a raw `pymongo.errors.DuplicateKeyError` escaping the
repository boundary untranslated — violating the "no driver exception
crosses this boundary" rule — not a downgrade to `AppError.unknown()`.

## Invariants that must never be broken

- **Core has zero Mongo/Beanie awareness.** Enforced mechanically: the root
  `pyproject.toml`'s import-linter configuration includes a `forbidden`
  contract making `beanie`/`pymongo` imports inside `trutina.core` a build
  failure. This package exists specifically so core never needs either.
- **Layered dependency direction.** The root import-linter `layers`
  contract fixes the order `trutina.cli | trutina.api` →
  `trutina.infrastructure` → `trutina.core` →
  `trutina.shared | trutina.config`. This package must never import from
  `trutina.cli` or `trutina.api`.
- **No business rules in a repository.** Uniqueness pre-checks, the
  one-posting-per-journal invariant, chart-of-accounts resolution — none
  of it belongs here. A repository's only job is mapping and persistence.
- **`_to_document()`/`_to_domain()` are the only mapping path.** No other
  code should hand-construct a `*Document` for persistence, or hand-build
  a domain object from a raw Mongo result.
- **Derived/computed domain fields are never persisted.** `normal_balance`,
  `total_debits`/`total_credits`/`is_balanced`, and `is_debit` are
  recomputed on reconstruction, never stored — confirmed by
  `test_does_not_include_normal_balance_field`,
  `test_does_not_include_total_debits_field`, and
  `test_does_not_include_is_debit_field` in each adapter's document tests.
  Storing them would create a second source of truth that could silently
  diverge from the fields they're derived from.
- **Callers must initialize Beanie first.** Every repository assumes
  `init_beanie()` has already registered its `Document` class. This
  package does not call `init_beanie()` itself — that is a
  composition-root responsibility (`CliContext`, the API's bootstrap),
  kept out of this package so it stays agnostic to when and how often a
  caller wants to initialize.

## Allowed and forbidden dependencies

**Allowed** (per `packages/infrastructure/pyproject.toml`): `trutina-shared`,
`trutina-core`, `trutina-config`, `beanie`, `pymongo`.

**Forbidden:** `trutina-cli`, `trutina-api`, or any other `apps/*` package;
any presentation library (`typer`, `rich`, `fastapi`, `strawberry-graphql`).
None of these appear as dependencies today, and none should be added — a
storage adapter has no legitimate reason to know about a transport or UI
layer.

## Layering within this package

There is no import-linter contract scoped _inside_ `trutina.infrastructure`
today — the root workspace's `layers` contract enforcing
`posting → journal → account` ordering is scoped to `trutina.core`, not to
this package. In practice, `mongo/journal/` and `mongo/posting/` each
import only their own domain package from core (e.g.
`mongo/posting/repository.py` imports `trutina.core.posting`, not
`trutina.core.journal`), mirroring core's dependency order — but this is
convention observed in the current source rather than something CI
currently fails a build over. Flagging this as convention, not enforcement.

## Control and data flow

```text
Service (trutina-core)
    -> Repo contract call (AccountRepo / JournalRepo / PostingRepo)
        -> Mongo*Repo method
            -> MongoExecutor.run(coroutine)
                -> translate_mongo_errors() context
                    -> Beanie / raw PyMongo call
            <- result
        <- _to_domain() reconstructs and re-validates the domain object
    <- ViewModel / domain object returned to the service
```

Write paths that can raise `DuplicateKeyError` (`create()`, `update()`,
`save()`) catch it _outside_ `MongoExecutor.run()` and delegate to a
per-repository `_on_duplicate()` method, which inspects the violated index
name (`violated_index()`) to decide which domain conflict to raise.

## Extension points

- **A second storage backend.** Any package implementing `AccountRepo`,
  `JournalRepo`, and `PostingRepo` against a different datastore is a
  legitimate sibling to this package — it would prove the contracts are
  genuinely storage-agnostic rather than MongoDB-shaped in disguise. No
  such package exists yet.
- **A new bounded-context adapter.** Mirrors the `account`/`journal`/
  `posting` shape exactly — see the README's "Extending" section.
- **Cross-cutting execution concerns.** `MongoExecutor` is the intended
  seam for adding logging, metrics, retries, or (eventually)
  transaction/session support to every repository at once, without
  touching individual repository methods. This is stated as
  forward-looking intent in `MongoExecutor`'s own docstring — no such
  behavior is implemented today.

## Assumptions this package relies on

- A caller has already run `init_beanie()` with the relevant `Document`
  classes registered before constructing any `Mongo*Repo`.
- Exactly one MongoDB connection/event-loop pairing is active per process
  at a time from this package's point of view; coordinating that (e.g. the
  CLI's single `BlockingPortal` vs. the API's ASGI-owned loop) is the
  caller's responsibility, not something this package arbitrates.
- `MongoSettings` is fully resolved before `connect()` is called — this
  package never reads environment variables or calls `get_settings()`
  itself.

## Common mistakes to avoid

- Assuming that skipping the repository's own `except DuplicateKeyError`
  clause causes a silent downgrade to `AppError.unknown()` — it doesn't;
  `translate_mongo_errors()` always re-raises `DuplicateKeyError`
  unchanged, so omitting the outer catch instead leaks a raw pymongo
  exception across the repository boundary.
- Adding an existence check, uniqueness check, or any other business rule
  inside a repository method instead of the calling service.
- Persisting a computed/derived domain field (`normal_balance`,
  `is_balanced`, `is_debit`, `total_debits`/`total_credits`).
- Calling Beanie or PyMongo directly from a repository method instead of
  routing through `MongoExecutor.run()` — this silently loses error
  translation.
- Forgetting to add a new `Document` subclass to the production
  `init_beanie()` call site and to
  `tests/fixtures/mongo.py::DOCUMENT_MODELS` when adding a new bounded
  context — the symptom is a `CollectionWasNotInitialized` error that only
  appears the first time the new repository is actually used.
