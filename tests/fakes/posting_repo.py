"""In-memory PostingRepo implementation for PostingService unit tests.

Provides a lightweight fake that satisfies the PostingRepo contract without
any storage backend. Test cases inspect ``saved_batches`` to verify that
the service persisted the correct records, and ``saved_created_by`` to
verify which actor the service attributed the write to.
"""

from trutina.core.posting.repo import PostingRepo
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.shared.rule import account_lookup_key


class FakePostingRepo(PostingRepo):
    """In-memory PostingRepo for PostingService unit tests.

    This fake behaves according to the PostingRepo contract and provides
    lightweight inspection hooks for assertions.

    All postings are stored in a flat list. Both ``get_by_account`` and
    ``get_by_journal_number`` perform linear scans over that list, which
    is appropriate for unit tests where the data set is small.

    ``get_by_account`` applies case-insensitive matching via
    ``account_lookup_key``, consistent with how ``FakeAccountRepo``
    handles account name lookups.

    Attributes:
        saved_batches: Each list passed to ``save_many``, in call order.
            Tests assert on ``saved_batches[0]`` to verify the batch
            size and on ``saved_batches`` length to verify the number
            of save calls.
        saved_created_by: The ``created_by`` argument of each
            ``save_many`` call, in call order. One entry per call, not
            per posting: index ``i`` belongs to ``saved_batches[i]``.
            Reads do not return it, matching the contract: ``created_by``
            is not part of the domain model.
    """

    def __init__(self) -> None:
        self._postings: list[LedgerPosting] = []
        self.saved_batches: list[list[LedgerPosting]] = []
        self.saved_created_by: list[str] = []

    async def save_many(
        self, postings: list[LedgerPosting], *, created_by: str
    ) -> None:
        self.saved_batches.append(list[LedgerPosting](postings))
        self.saved_created_by.append(created_by)
        self._postings.extend(postings)

    async def get_by_account(self, account: str) -> list[LedgerPosting]:
        key = account_lookup_key(account)
        return [p for p in self._postings if account_lookup_key(p.account) == key]

    async def get_by_journal_number(self, journal_number: int) -> list[LedgerPosting]:
        return [p for p in self._postings if p.journal_number == journal_number]
