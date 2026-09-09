"""Beanie document and embedded subdocument for the Journal aggregate.

``JournalDocument`` is the MongoDB persistence representation of a
``JournalEntry`` domain object. ``JournalLineSubDocument`` is the embedded
Pydantic model representing a single line within that document.

Neither class performs business validation. All domain invariants —
entry balance, posting-date constraints, minimum line count — are enforced
by the domain models before any document reaches this layer.

Fields persisted
----------------
JournalDocument
    journal_number  — Business sequence identifier. Unique, indexed.
    posting_date    — Effective accounting date. Indexed for future
                        date-range queries (reporting, trial balance).
    description     — Optional narrative. Not indexed.
    lines           — Embedded list of ``JournalLineSubDocument`` instances.

JournalLineSubDocument
    account         — Normalized account name carried from the domain
                        ``JournalLine``. Stored as-is; no ``account_key``
                        denormalization is needed because journal lines are
                        never queried in isolation by account name through
                        this repository. The posting layer handles per-account
                        queries via its own collection.
    debit_amount    — Stored as a string to preserve ``Decimal`` precision.
                        MongoDB has no native lossless decimal type accessible
                        via Beanie's default codec, so amounts are encoded as
                        strings (e.g. ``"100.50"``) and decoded with
                        ``Decimal(value)`` on load.
    credit_amount   — Same string encoding as ``debit_amount``.

Fields NOT persisted
--------------------
JournalEntry.total_debits, .total_credits, .is_balanced
    Computed ``@computed_field`` properties derived from ``lines``.
    Persisting them would introduce a second source of truth that could
    diverge from the underlying line data. They are recomputed when the
    domain model is reconstructed by ``MongoJournalRepo._to_domain()``.
    This mirrors the decision to omit ``normal_balance`` from
    ``AccountDocument``.

Embedding strategy
------------------
Journal lines are embedded inside ``JournalDocument`` rather than stored in
a separate collection because they have no independent identity, are always
accessed with their parent entry, and are never queried in isolation through
the journal repository. ``JournalLineSubDocument`` is a plain Pydantic
``BaseModel`` — not a Beanie ``Document`` — because it is never persisted as
a top-level MongoDB document.

Identity strategy
-----------------
``_id`` uses Beanie's default ``PydanticObjectId``. It is an internal
persistence identifier and never crosses the repository boundary. Domain
models and services identify journal entries exclusively by the business
``journal_number``.

Decimal encoding
----------------
Amounts are stored as strings. If the encoding strategy changes (for example,
to BSON ``Decimal128``), all stored amount strings must be migrated before the
new codec is activated. ``MongoJournalRepo._to_domain()`` decodes amounts with
``Decimal(value)``; any malformed stored string will raise ``ValueError``
before the domain model is constructed, surfacing data corruption immediately.

Migration note
--------------
The ``idx_journal_posting_date`` index anticipates date-range queries needed
by future trial-balance and reporting workflows. It can be deferred if the
reporting workstream has not started, but is included now because it costs
negligible write overhead and avoids a collection scan the moment date-range
queries are introduced.
"""

from datetime import datetime

from pydantic import BaseModel
from pymongo import ASCENDING, IndexModel
from trutina.infrastructure.mongo.shared import TimestampedDocument


class JournalLineSubDocument(BaseModel):
    """Embedded representation of a single journal line in MongoDB.

    Stored inside ``JournalDocument.lines`` as an embedded array element.
    Never persisted as a top-level MongoDB document, which is why this class
    extends ``pydantic.BaseModel`` rather than ``beanie.Document``.

    Monetary amounts are stored as strings to preserve ``Decimal`` precision.
    The domain model re-validates amounts on reconstruction, so any corrupt
    stored value surfaces as a ``ValueError`` during ``Decimal()`` parsing
    rather than silently propagating through the accounting workflow.

    Attributes:
        account: Normalized account name, carried unchanged from the domain
            ``JournalLine``.
        debit_amount: Debit amount encoded as a decimal string, e.g.
            ``"100.50"``. Zero is stored as ``"0"``.
        credit_amount: Credit amount encoded as a decimal string, e.g.
            ``"0"``. One of ``debit_amount`` or ``credit_amount`` is always
            ``"0"`` on a valid line; the domain model enforces this before
            persistence.
    """

    account: str
    debit_amount: str
    credit_amount: str


class JournalDocument(TimestampedDocument):
    """MongoDB persistence model for a Journal Entry.

    ``JournalDocument`` defines how a validated ``JournalEntry`` domain object
    is represented in MongoDB. It forms the persistence boundary between the
    journal domain and the underlying database and intentionally contains no
    business validation or accounting rules.

    Domain services and the application operate on ``JournalEntry`` and
    related DTOs. Beanie and MongoDB operate on ``JournalDocument`` instances.

    Lines are embedded as a list of ``JournalLineSubDocument`` instances
    rather than stored in a separate collection, because they have no
    independent identity and are always accessed with their parent entry.
    Journal entries are immutable after save, so ``updated_at`` will always
    equal ``created_at`` in practice — the ``TimestampedDocument`` hook sets
    both on insert and no update path exists in ``JournalRepo``.
    """

    journal_number: int
    posting_date: datetime
    description: str | None = None
    lines: list[JournalLineSubDocument]

    class Settings:
        """Configure MongoDB persistence for journal entry documents.

        Stores journal documents in the ``journal_entries`` collection and
        defines the database indexes required to enforce repository-level
        uniqueness and support expected query patterns.

        ``uq_journal_number`` enforces uniqueness of the business identifier
        and supports the primary point-lookup query pattern.

        ``idx_journal_posting_date`` is a non-unique index that anticipates
        date-range queries needed by future trial-balance and reporting
        workflows. It is included now to avoid a collection scan when
        reporting queries are introduced.
        """

        name = "journal_entries"
        indexes = [
            IndexModel(
                [("journal_number", ASCENDING)],
                unique=True,
                name="uq_journal_number",
            ),
            IndexModel(
                [("posting_date", ASCENDING)],
                unique=False,
                name="idx_journal_posting_date",
            ),
        ]
