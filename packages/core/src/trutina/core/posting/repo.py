"""Repository contract for the posting feature.

Defines the persistence boundary used by PostingService. All ledger
posting storage operations pass through this contract, regardless of
the underlying storage technology.

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

from .schemas.ledger_posting import LedgerPosting


class PostingRepo(ABC):
    """Persistence contract for LedgerPosting records.

    Defines the storage operations required by posting workflows.

    Implementations must:

    - Remain asynchronous.
    - Avoid business-rule enforcement.
    - Return empty collections on lookup misses where documented.
    - Translate storage-specific failures into AppError.
    - Remain independent of CLI, Rich, and Typer concerns.

    The contract defines persistence behavior only. Derivation of
    postings from journal entries remains the responsibility of
    PostingService.
    """

    @abstractmethod
    async def save_many(
        self, postings: list[LedgerPosting], *, created_by: str
    ) -> None:
        """Persist a batch of ledger postings.

        All postings in the batch are derived from a single journal entry.
        This contract does not require transaction support or promise
        all-or-nothing persistence; adapter guarantees are implementation
        specific.

        ``created_by`` records which caller posted the entry. It is an
        opaque string supplied by PostingService, which has already
        checked that it is non-blank; adapters store it as given, once
        per posting, and never inspect its format. It is not a field of
        the LedgerPosting domain model, so reading postings back does
        not return it. An adapter that cannot store it must say so in
        its own documentation.

        Args:
            postings: A list of fully validated LedgerPosting records
                derived from a single journal entry.
            created_by: Opaque identifier of the caller performing the
                write.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def get_by_account(self, account: str) -> list[LedgerPosting]:
        """Return all postings for a given account in date order.

        Args:
            account: The normalized account name to filter by.

        Returns:
            All LedgerPosting records whose ``account`` field matches,
            ordered ascending by ``posting_date``. Returns an empty
            list when no postings exist for the account.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...

    @abstractmethod
    async def get_by_journal_number(self, journal_number: int) -> list[LedgerPosting]:
        """Return all postings derived from a given journal entry.

        Args:
            journal_number: The journal entry number to filter by.

        Returns:
            All LedgerPosting records whose ``journal_number`` field
            matches, in the order they were originally saved. Returns
            an empty list when no postings exist for that journal
            number.

        Raises:
            AppError: STORAGE_UNAVAILABLE if the backend cannot be
                reached.
        """
        ...
