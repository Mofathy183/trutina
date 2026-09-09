"""Concrete MongoDB implementation of the JournalRepo contract.

``MongoJournalRepo`` bridges the journal domain and MongoDB by translating
validated ``JournalEntry`` domain models into ``JournalDocument`` persistence
models and reconstructing them on retrieval. It performs no business
validation — that responsibility belongs to ``JournalService`` and the domain
schemas.

Query strategy
--------------
``journal_number`` is the primary business identifier for all operations,
matching the public ``JournalRepo`` contract. The ``uq_journal_number`` unique
index provides efficient point lookups and enforces storage-level uniqueness.

``_id`` remains an internal MongoDB implementation detail and never appears
in repository contracts or domain models.

Mapping boundary
----------------
``_to_document()`` and ``_to_domain()`` are the single sources of truth for
converting between the journal domain model and its persistence representation.
``save()`` uses ``_to_document()``. Every retrieval method uses ``_to_domain()``.

Decimal encoding
----------------
Monetary amounts are stored as strings to preserve ``Decimal`` precision.
``_to_document()`` converts ``Decimal → str``; ``_to_domain()`` converts
``str → Decimal``. Float coercion at any point in this chain would silently
corrupt amounts and violate accounting accuracy requirements. The domain model
re-runs validation on reconstruction, so any malformed stored string surfaces
immediately as a ``ValueError`` from ``Decimal()`` rather than propagating.

Journal number allocation
-------------------------
``next_journal_number()`` uses a dedicated ``counters`` collection with an
atomic ``findOneAndUpdate`` / ``$inc`` operation. The counter document key is
``{"_id": "journal_number"}``. The ``seq`` field starts at ``0`` on first
creation (via ``upsert=True``) and is incremented before the updated value is
returned, so the first call produces ``1``.

This method accesses the raw PyMongo async collection rather than going through
a Beanie ``Document`` class because Beanie does not provide a primitive for
atomic counter increments on non-document collections. Error translation is
applied via ``translate_mongo_errors()`` directly, which is the same context
manager used internally by ``MongoExecutor``.

Immutability
------------
``JournalEntry`` is immutable once saved. ``JournalRepo`` defines no
``update()`` method and this repository implements no update path. The
``TimestampedDocument`` hook sets ``created_at`` and ``updated_at`` once on
insert; neither field changes afterward. In practice ``updated_at`` will always
equal ``created_at`` on journal documents.

DuplicateKeyError handling
--------------------------
``DuplicateKeyError`` is caught in ``save()`` and delegated to
``_on_duplicate()``, which inspects the violated index name via
``violated_index()`` and returns the appropriate ``AppError``. This mirrors
the pattern established by ``MongoAccountRepo``. A violation on the
``journal_number`` index indicates a defect in the counter allocation
sequence and is mapped to ``ErrorCode.DUPLICATE_JOURNAL_NUMBER``. Violations
on unrecognized indexes fall through to ``AppError.unknown()``.

Callers must ensure ``init_beanie()`` has been executed with
``JournalDocument`` registered before constructing this repository.
"""

from datetime import UTC, datetime
from decimal import Decimal

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from trutina.core.journal.repo import JournalRepo
from trutina.core.journal.schemas import JournalEntry, JournalLine
from trutina.infrastructure.mongo.error_translation import (
    translate_mongo_errors,
    violated_index,
)
from trutina.infrastructure.mongo.journal.document import (
    JournalDocument,
    JournalLineSubDocument,
)
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.errors import AppError, ErrorCode

_COUNTER_KEY = "journal_number"


class MongoJournalRepo(JournalRepo):
    """Beanie-backed implementation of the JournalRepo persistence contract.

    Fulfills the ``JournalRepo`` interface by translating between validated
    ``JournalEntry`` domain objects and ``JournalDocument`` persistence
    documents. Contains no accounting rules or business validation. All
    storage-specific failures are translated into ``AppError`` before
    crossing the repository boundary.

    Every Beanie operation is executed through ``MongoExecutor`` so MongoDB
    error translation is applied consistently. The counter operation in
    ``next_journal_number()`` uses ``translate_mongo_errors()`` directly
    because it targets a non-document collection via raw Motor API.

    Args:
        executor: Infrastructure collaborator responsible for executing
            Beanie operations with consistent MongoDB error translation.
    """

    def __init__(self, executor: MongoExecutor) -> None:
        self._executor = executor

    async def save(self, entry: JournalEntry) -> None:
        """Persist a validated journal entry as a new MongoDB document.

        Args:
            entry: Fully validated ``JournalEntry`` domain model. Must carry
                a ``journal_number`` previously obtained from
                ``next_journal_number()``.

        Raises:
            AppError: DUPLICATE_JOURNAL_NUMBER if a collision occurs on the
                ``journal_number`` index, indicating a defect in the counter
                allocation sequence.
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the database
                cannot complete the write.
        """
        doc = self._to_document(entry)
        try:
            await self._executor.run(doc.insert())
        except DuplicateKeyError as exc:
            raise self._on_duplicate(exc, entry) from exc

    async def get_by_number(self, journal_number: int) -> JournalEntry | None:
        """Fetch a single journal entry by its journal number.

        Args:
            journal_number: The journal number to look up.

        Returns:
            The reconstructed ``JournalEntry`` if found; otherwise ``None``.
            ``None`` is a valid return value — the service decides whether to
            raise ``AppError``.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the database
                cannot be reached.
        """
        doc = await self._executor.run(
            JournalDocument.find_one(JournalDocument.journal_number == journal_number)
        )
        return self._to_domain(doc) if doc else None

    async def list_entries(self) -> list[JournalEntry]:
        """Return all persisted journal entries ordered by journal number.

        Returns:
            Every journal entry currently in the store, ordered ascending
            by ``journal_number``. Returns an empty list when no entries
            have been persisted.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the database
                cannot be reached.
        """
        docs = await self._executor.run(
            JournalDocument.find().sort("+journal_number").to_list()
        )
        return [self._to_domain(doc) for doc in docs]

    async def next_journal_number(self) -> int:
        """Return the next available journal number via an atomic counter.

        Uses ``findOneAndUpdate`` with ``$inc`` on a dedicated ``counters``
        collection. The counter document is created on first use (``upsert=True``)
        with ``seq`` starting at ``0``. The field is incremented before the
        updated document is returned, so the first call produces ``1`` and
        each subsequent call produces the next integer in sequence.

        The ``counters`` collection is not a Beanie-registered document
        collection. It is accessed through the raw Motor async collection API,
        with ``translate_mongo_errors()`` applied directly for error
        translation.

        Returns:
            A positive integer not yet used by any persisted entry.

        Raises:
            AppError: STORAGE_UNAVAILABLE or STORAGE_TIMEOUT if the database
                cannot be reached.
        """
        collection = JournalDocument.get_pymongo_collection()
        counters = collection.database["counters"]

        async with translate_mongo_errors():
            result = await counters.find_one_and_update(
                {"_id": _COUNTER_KEY},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )

        return result["seq"]

    @staticmethod
    def _to_document(entry: JournalEntry) -> JournalDocument:
        """Map a validated ``JournalEntry`` to its MongoDB persistence model.

        The single mapping boundary from the journal domain to the persistence
        layer. Every field written to MongoDB originates here.

        Decimal amounts are encoded as strings to preserve precision. Computed
        fields (``total_debits``, ``total_credits``, ``is_balanced``) are
        omitted because they are derived from ``lines`` and would create a
        second source of truth if stored independently.

        ``updated_at`` is set to the current UTC time. The
        ``TimestampedDocument.initialize_timestamps()`` hook will set
        ``created_at`` to the same moment on insert. Journal entries are
        immutable after save, so neither field advances beyond the initial
        insert values.

        Args:
            entry: Validated ``JournalEntry`` domain model to map.

        Returns:
            The corresponding ``JournalDocument`` ready for persistence.
        """
        return JournalDocument(
            journal_number=entry.journal_number,
            posting_date=entry.posting_date,
            description=entry.description,
            lines=[
                JournalLineSubDocument(
                    account=line.account,
                    debit_amount=str(line.debit_amount),
                    credit_amount=str(line.credit_amount),
                )
                for line in entry.lines
            ],
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _to_domain(doc: JournalDocument) -> JournalEntry:
        """Reconstruct a ``JournalEntry`` domain model from persisted data.

        Domain validation re-runs during reconstruction so journal invariants
        (balance, posting-date constraints, minimum line count) remain enforced
        regardless of what is stored. Computed fields are derived fresh from
        the reconstructed lines rather than loaded from persistence.

        Amount strings are decoded with ``Decimal(value)``. If a stored amount
        string is malformed (e.g., due to a storage corruption or failed
        migration), ``ValueError`` propagates from ``Decimal()`` before the
        domain model is constructed, surfacing the corruption immediately.

        Args:
            doc: Persisted ``JournalDocument`` to reconstruct from.

        Returns:
            The reconstructed ``JournalEntry`` domain model.
        """
        return JournalEntry(
            journal_number=doc.journal_number,
            posting_date=doc.posting_date,
            description=doc.description,
            lines=[
                JournalLine(
                    account=line.account,
                    debit_amount=Decimal(line.debit_amount),
                    credit_amount=Decimal(line.credit_amount),
                )
                for line in doc.lines
            ],
        )

    def _on_duplicate(self, exc: DuplicateKeyError, entry: JournalEntry) -> AppError:
        """Translate a storage uniqueness violation into a domain conflict error.

        Inspects the violated MongoDB index to determine which uniqueness
        constraint failed and converts it into the appropriate ``AppError``.
        Violations on unrecognized indexes are treated as infrastructure
        failures rather than domain conflicts.

        Args:
            exc: Duplicate key exception raised by MongoDB.
            entry: The journal entry involved in the failed write.

        Returns:
            The corresponding domain ``AppError``.
        """
        field = violated_index(exc)
        match field:
            case "journal_number":
                return AppError.conflict(
                    code=ErrorCode.DUPLICATE_JOURNAL_NUMBER,
                    resource="journal_entry",
                    field_name="journal_number",
                    value=str(entry.journal_number),
                )
            case _:
                return AppError.unknown(cause=exc)
