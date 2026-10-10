from trutina.core.journal.repo import JournalRepo
from trutina.core.journal.schemas import JournalEntry


class FakeJournalRepo(JournalRepo):
    """In-memory JournalRepo for JournalService unit tests.

    This fake behaves according to the JournalRepo contract and provides
    lightweight inspection hooks for assertions.

    Journal numbers are issued sequentially starting from 1. The counter
    advances each time :meth:`next_journal_number` is called, regardless
    of whether the issued number is subsequently saved.

    Attributes:
        saved_entries: Every entry passed to ``save``, in call order.
        saved_created_by: The ``created_by`` argument of every ``save``
            call, in call order. Index ``i`` belongs to
            ``saved_entries[i]``. Reads do not return it, matching the
            contract: ``created_by`` is not part of the domain model.
    """

    def __init__(self) -> None:
        self._entries: dict[int, JournalEntry] = {}
        self._next_number: int = 1

        self.saved_entries: list[JournalEntry] = []
        self.saved_created_by: list[str] = []

    async def save(self, entry: JournalEntry, *, created_by: str) -> None:
        self.saved_entries.append(entry)
        self.saved_created_by.append(created_by)
        self._entries[entry.journal_number] = entry

    async def get_by_number(self, journal_number: int) -> JournalEntry | None:
        return self._entries.get(journal_number)

    async def list_entries(self) -> list[JournalEntry]:
        return sorted(self._entries.values(), key=lambda e: e.journal_number)

    async def next_journal_number(self) -> int:
        number = self._next_number
        self._next_number += 1
        return number
