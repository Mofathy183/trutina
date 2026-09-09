"""Beanie document for the LedgerPosting aggregate.

``PostingDocument`` is the MongoDB persistence representation of a
``LedgerPosting`` domain object. It performs no business validation —
every field value arrives already validated by ``LedgerPosting`` before
``MongoPostingRepo._to_document()`` ever constructs one.

Fields persisted
-----------------
account        — Display name of the account, carried unchanged from the
                 domain ``LedgerPosting``. Already normalized by
                 ``clean_account_name()`` before this layer ever sees it.
account_key    — ``account_lookup_key(account)``, denormalized for
                 case-insensitive lookup without collection-level
                 collation. Infrastructure-only; never exposed outside
                 this module. Mirrors ``name_key`` on ``AccountDocument``.
debit_amount   — ``LedgerPosting.debit_amount`` encoded as a decimal
                 string (e.g. ``"100.50"``, or ``"0"`` on a credit
                 posting). MongoDB has no native lossless decimal type
                 accessible via Beanie's default codec, so amounts are
                 stored as strings and decoded with ``Decimal(value)`` on
                 load — the same strategy used by
                 ``JournalLineSubDocument``.
credit_amount  — Same string encoding as ``debit_amount``. Exactly one of
                 ``debit_amount``/``credit_amount`` is ``"0"`` on any
                 valid document; the domain model enforces this before
                 persistence.
journal_number — Back-reference to the originating ``JournalEntry``.
                 Indexed for ``get_by_journal_number()``.
posting_date   — Effective accounting date inherited from the
                 originating journal entry. Indexed together with
                 ``account_key`` to satisfy the ascending-date ordering
                 required by ``get_by_account()``.
line_index     — Zero-based position of this posting within the batch
                 passed to ``save_many()``. This is an infrastructure-only
                 field with no equivalent on the ``LedgerPosting`` domain
                 model. It exists solely to give ``get_by_journal_number()``
                 a deterministic sort key, satisfying the repository
                 contract's "in the order they were originally saved"
                 guarantee. MongoDB does not guarantee insertion order on
                 its own, so this field must be populated explicitly by
                 ``MongoPostingRepo._to_document()``.

Fields NOT persisted
---------------------
is_debit — A computed property on ``LedgerPosting`` derived from
           ``debit_amount > 0``. Persisting it would introduce a second
           source of truth that could diverge from the stored amounts.
           Mirrors the omission of ``normal_balance`` from
           ``AccountDocument`` and of ``total_debits``/``total_credits``/
           ``is_balanced`` from ``JournalDocument``. Recomputed by
           ``MongoPostingRepo._to_domain()``.

Identity strategy
------------------
``_id`` uses Beanie's default ``PydanticObjectId``. It is an internal
persistence identifier and never crosses the repository boundary.
Postings are identified externally by ``account`` or ``journal_number``,
never by their MongoDB identifier.

Immutability
------------
``LedgerPosting`` is frozen and ``PostingRepo`` defines no update method,
so neither timestamp is ever advanced after the initial write — in
practice ``updated_at`` always equals ``created_at`` on posting
documents, the same property already true of ``JournalDocument``.

Note that the inherited ``TimestampedDocument.initialize_timestamps()``
hook only fires on a single-document ``insert()``, not on
``insert_many()``. Because ``MongoPostingRepo.save_many()`` writes the
whole batch via ``insert_many()``, ``MongoPostingRepo._to_document()``
sets ``created_at``/``updated_at`` explicitly rather than relying on
that hook — see ``repository.py`` for details.

Decimal encoding
-----------------
Amounts are stored as strings. ``MongoPostingRepo._to_domain()`` decodes
them with ``Decimal(value)``. A malformed stored string raises
``ValueError`` before a domain object is constructed, surfacing storage
corruption immediately rather than propagating it silently.
"""

from datetime import datetime

from pymongo import ASCENDING, IndexModel
from trutina.infrastructure.mongo.shared import TimestampedDocument


class PostingDocument(TimestampedDocument):
    """MongoDB persistence model for a single ledger posting.

    ``PostingDocument`` defines how a validated ``LedgerPosting`` domain
    object is represented in MongoDB. It forms the persistence boundary
    between the posting domain and the underlying database and
    intentionally contains no business validation or accounting rules.

    Postings are stored as flat, independent documents rather than
    embedded inside their originating journal document, because they are
    queried along two distinct access paths — by account and by journal
    number — that would otherwise require expensive scans or aggregation
    pipelines over embedded arrays.
    """

    account: str
    account_key: str
    debit_amount: str
    credit_amount: str
    journal_number: int
    posting_date: datetime
    line_index: int

    class Settings:
        """Configure MongoDB persistence for posting documents.

        Stores posting documents in the ``postings`` collection and
        defines the indexes required to support the repository's two
        query patterns efficiently.

        ``idx_posting_account_key_date`` is a compound, non-unique index
        that serves ``get_by_account()`` — both the equality filter on
        ``account_key`` and the ascending sort on ``posting_date`` are
        absorbed by this single index, avoiding a separate in-memory sort
        stage. It also anticipates future trial-balance and
        account-balance reporting queries that filter by account and a
        ``posting_date`` range.

        ``idx_posting_journal_number`` is a non-unique index that serves
        ``get_by_journal_number()``. It is non-unique because a single
        journal entry produces one posting per line, so multiple posting
        documents legitimately share the same ``journal_number``.

        No unique index is defined anywhere on this collection. The
        one-posting-per-journal-entry check is performed by
        ``PostingService`` before persistence; storage does not enforce it.
        """

        name = "postings"
        indexes = [
            IndexModel(
                [("account_key", ASCENDING), ("posting_date", ASCENDING)],
                unique=False,
                name="idx_posting_account_key_date",
            ),
            IndexModel(
                [("journal_number", ASCENDING)],
                unique=False,
                name="idx_posting_journal_number",
            ),
        ]
