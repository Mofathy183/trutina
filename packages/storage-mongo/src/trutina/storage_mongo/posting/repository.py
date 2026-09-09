"""Concrete MongoDB implementation of the PostingRepo contract.

``MongoPostingRepo`` bridges the posting domain and MongoDB by translating
validated ``LedgerPosting`` domain objects into ``PostingDocument``
persistence models and reconstructing them on retrieval. It performs no
business validation — that responsibility belongs to ``PostingService``
and the ``LedgerPosting`` domain model. It does not enforce the
one-posting-per-journal-entry invariant; that check happens in
``PostingService`` before ``save_many()`` is ever called.

Query strategy
--------------
``get_by_account()`` filters and sorts using the
``idx_posting_account_key_date`` compound index: an equality match on the
denormalized, case-folded ``account_key`` followed by an ascending sort on
``posting_date``, exactly as required by the ``PostingRepo`` contract.

``get_by_journal_number()`` filters on the ``idx_posting_journal_number``
index and sorts ascending on ``line_index`` — an infrastructure-only field
populated by ``_to_document()`` — to deterministically reproduce the
order in which the postings were originally saved. MongoDB does not
guarantee insertion order on its own, so this explicit field and sort are
required to satisfy the contract.

Mapping boundary
-----------------
``_to_document()`` and ``_to_domain()`` are the single sources of truth
for converting between the posting domain and its persistence
representation. ``save_many()`` uses ``_to_document()`` once per posting
in the batch, supplying each posting's zero-based position as
``line_index``. Every retrieval method uses ``_to_domain()``.

Decimal encoding
-----------------
Monetary amounts are stored as strings to preserve ``Decimal`` precision.
``_to_document()`` converts ``Decimal -> str``; ``_to_domain()`` converts
``str -> Decimal``. A malformed stored amount string surfaces immediately
as a ``ValueError`` from ``Decimal()`` rather than propagating silently.

Timestamp population on batch insert
-------------------------------------
``TimestampedDocument.initialize_timestamps()`` is a Beanie
``@before_event(Insert)`` hook, which only fires for ``Document.insert()``
calls on a single document. ``save_many()`` writes the whole batch via
``PostingDocument.insert_many()``, which does **not** trigger
per-document ``before_event`` hooks — relying on the inherited hook here
would silently leave every ``created_at`` as ``None``. ``_to_document()``
therefore sets both ``created_at`` and ``updated_at`` explicitly to the
same timestamp before the document ever reaches ``insert_many()``,
rather than depending on the hook.

Duplicate-key handling
-----------------------
``PostingDocument`` defines no unique indexes, so ``DuplicateKeyError``
cannot occur during normal operation. Unlike ``MongoAccountRepo`` and
``MongoJournalRepo``, this repository defines no ``_on_duplicate()``
method — there is no uniqueness violation to translate.

Atomicity limitation
---------------------
``save_many()`` issues a single ``insert_many()`` call, which is not a
multi-document atomic operation on a standalone MongoDB deployment
without an explicit ``ClientSession``. If the process is interrupted
mid-insert, some posting documents from a batch may be persisted while
others are not. The current infrastructure has no transaction support
anywhere, so this limitation is accepted rather than worked around.
``PostingService`` checks ``get_by_journal_number()`` before calling
``save_many()``, which makes a partial write detectable (as an
erroneous "already posted" result) on a subsequent attempt, but this is
not a correctness guarantee.

Concurrency note
-----------------
The existence check in ``PostingService.post_journal_entry()`` and the
subsequent ``save_many()`` call are not atomic with respect to each
other. Two concurrent calls for the same journal number can both pass the
check before either writes, producing duplicate postings, because no
unique index exists to guard against this at the storage layer. This
mirrors the same documented TOCTOU window in
``AccountService.create_account()``.

Callers must ensure ``init_beanie()`` has been executed with
``PostingDocument`` registered before constructing this repository.
"""

from datetime import UTC, datetime
from decimal import Decimal

from trutina.core.posting.repo import PostingRepo
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.infrastructure.mongo.posting.document import PostingDocument
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.rule import account_lookup_key


class MongoPostingRepo(PostingRepo):
    """Beanie-backed implementation of the PostingRepo persistence contract.

    Fulfills the ``PostingRepo`` interface by translating between
    validated ``LedgerPosting`` domain objects and ``PostingDocument``
    persistence documents. Contains no accounting rules or business
    validation. All storage-specific failures are translated into
    ``AppError`` before crossing the repository boundary.

    Every Beanie operation is executed through ``MongoExecutor`` so
    MongoDB error translation is applied consistently. No duplicate-key
    handling is required because ``PostingDocument`` defines no unique
    indexes.

    Args:
        executor: Infrastructure collaborator responsible for executing
            Beanie operations with consistent MongoDB error translation.
    """

    def __init__(self, executor: MongoExecutor) -> None:
        self._executor = executor

    async def save_many(self, postings: list[LedgerPosting]) -> None:
        """Persist a batch of derived postings.

        All postings in the batch are mapped to ``PostingDocument``
        instances, each tagged with its zero-based position in the
        supplied list via ``line_index``, and written in a single
        ``insert_many()`` call.

        An empty batch is a no-op — no database call is made.

        Args:
            postings: A list of fully validated ``LedgerPosting`` records
                derived from a single journal entry. May be empty.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot complete the write.
        """
        if not postings:
            return

        docs = [
            self._to_document(posting, line_index)
            for line_index, posting in enumerate[LedgerPosting](postings)
        ]

        await self._executor.run(PostingDocument.insert_many(docs))

    async def get_by_account(self, account: str) -> list[LedgerPosting]:
        """Return all postings for an account, ordered by posting date.

        Matching is case-insensitive: the supplied account name is
        normalized with ``account_lookup_key()`` before lookup, following
        the same case-insensitive semantics used throughout the chart of
        accounts.

        Args:
            account: The account name to filter by, in any casing.

        Returns:
            All postings for the account, ordered ascending by
            ``posting_date``. Returns an empty list when no postings
            exist for the account.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot be reached.
        """
        key = account_lookup_key(account)

        docs = await self._executor.run(
            PostingDocument.find(PostingDocument.account_key == key)
            .sort("+posting_date")
            .to_list()
        )

        return [self._to_domain(doc) for doc in docs]

    async def get_by_journal_number(self, journal_number: int) -> list[LedgerPosting]:
        """Return all postings derived from a given journal entry.

        Results are sorted ascending by ``line_index``, an
        infrastructure-only field that records each posting's original
        position within the batch passed to ``save_many()``. This
        reproduces the order in which the postings were originally saved,
        since MongoDB provides no insertion-order guarantee of its own.

        Args:
            journal_number: The journal entry number to filter by.

        Returns:
            All postings derived from that journal entry, in their
            original save order. Returns an empty list when no postings
            exist for that journal number.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the
                database cannot be reached.
        """
        docs = await self._executor.run(
            PostingDocument.find(PostingDocument.journal_number == journal_number)
            .sort("+line_index")
            .to_list()
        )

        return [self._to_domain(doc) for doc in docs]

    @staticmethod
    def _to_document(posting: LedgerPosting, line_index: int) -> PostingDocument:
        """Map a validated LedgerPosting to its MongoDB persistence model.

        The single mapping boundary from the posting domain to the
        persistence layer. Every field written to MongoDB originates
        here. ``line_index`` has no domain-model equivalent; it is
        supplied by the caller as the posting's zero-based position
        within its save batch, solely to give
        ``get_by_journal_number()`` a deterministic sort key.

        Decimal amounts are encoded as strings to preserve precision.
        ``is_debit`` is omitted because it is derived from the amount
        fields rather than stored independently. ``created_at`` and
        ``updated_at`` are both set explicitly to the current UTC time
        here rather than left to ``TimestampedDocument``'s
        ``before_event(Insert)`` hook, because ``save_many()`` persists
        the batch via ``insert_many()``, which does not trigger that
        hook.

        Args:
            posting: Validated ``LedgerPosting`` domain model to map.
            line_index: Zero-based position of this posting within the
                batch passed to ``save_many()``.

        Returns:
            The corresponding ``PostingDocument`` ready for persistence.
        """
        now = datetime.now(UTC)
        return PostingDocument(
            account=posting.account,
            account_key=account_lookup_key(posting.account),
            debit_amount=str(posting.debit_amount),
            credit_amount=str(posting.credit_amount),
            journal_number=posting.journal_number,
            posting_date=posting.posting_date,
            line_index=line_index,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _to_domain(doc: PostingDocument) -> LedgerPosting:
        """Reconstruct a LedgerPosting domain model from persisted data.

        Domain validation re-runs during reconstruction so posting
        invariants (single-sided amounts, valid account name, supported
        posting-date range) remain enforced regardless of what is stored.
        ``line_index`` is an infrastructure-only field and is
        intentionally not passed through to the domain model.

        Amount strings are decoded with ``Decimal(value)``. If a stored
        amount string is malformed, ``ValueError`` propagates from
        ``Decimal()`` before the domain model is constructed, surfacing
        the corruption immediately.

        Args:
            doc: Persisted ``PostingDocument`` to reconstruct from.

        Returns:
            The reconstructed ``LedgerPosting`` domain model.
        """
        return LedgerPosting(
            account=doc.account,
            debit_amount=Decimal(doc.debit_amount),
            credit_amount=Decimal(doc.credit_amount),
            journal_number=doc.journal_number,
            posting_date=doc.posting_date,
        )
