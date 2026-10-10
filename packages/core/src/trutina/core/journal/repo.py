"""Repository contract for the journal feature.

Defines the persistence boundary used by JournalService. All journal
storage operations pass through this contract, regardless of the
underlying storage technology.

Implementations must remain asynchronous, must not contain business
rules, and must translate storage-specific failures into AppError
instances before they cross this boundary.

Exception Contract
------------------

Concrete implementations must translate storage-specific failures into
AppError before they cross the repository boundary.

Services depend only on AppError and must never be coupled to storage
libraries, database drivers, or transport-specific exceptions.

The exact translation strategy is implementation-specific.
"""

from abc import ABC, abstractmethod

from .schemas.journal import JournalEntry


class JournalRepo(ABC):
    """Persistence contract for JournalEntry records.

    Defines the storage operations required by journal workflows.

    Implementations must:

    - Remain asynchronous.
    - Avoid business-rule enforcement.
    - Return None on lookup misses where documented.
    - Translate storage-specific failures into AppError.
    - Remain independent of CLI, Rich, and Typer concerns.

    The contract defines persistence behavior only. Allocation of
    journal numbers and storage implementation details remain the
    responsibility of concrete adapters.
    """

    @abstractmethod
    async def save(self, entry: JournalEntry, *, created_by: str) -> None:
        """Persist a validated journal entry.

        The entry must carry a journal number previously obtained from
        :meth:`next_journal_number`. Implementations must translate a
        storage-level duplicate-key violation into AppError before it
        leaves this method.

        ``created_by`` records which caller performed the write. It is
        an opaque string supplied by JournalService, which has already
        checked that it is non-blank; adapters store it as given and
        never inspect its format. It is not a field of the JournalEntry
        domain model, so reading an entry back does not return it. An
        adapter that cannot store it must say so in its own
        documentation.

        Args:
            entry: A fully validated domain JournalEntry.
            created_by: Opaque identifier of the caller performing the
                write.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def get_by_number(self, journal_number: int) -> JournalEntry | None:
        """Fetch a single journal entry by its journal number.

        Args:
            journal_number: The journal number to look up.

        Returns:
            The matching JournalEntry, or None if no entry has that
            number. None is a valid return value, not an error condition
            — the service decides whether to raise AppError.not_found().

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def list_entries(self) -> list[JournalEntry]:
        """Return all persisted journal entries in journal-number order.

        Returns:
            Every journal entry currently in the store, ordered
            ascending by journal number.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def next_journal_number(self) -> int:
        """Return the next available journal number for assignment.

        The returned value is guaranteed to be a positive integer not
        yet used by any persisted entry. Implementations are responsible
        for ensuring that sequential calls return distinct values and
        that the mechanism is safe against concurrent access.

        Returns:
            A positive integer suitable for use as a new journal number.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...
