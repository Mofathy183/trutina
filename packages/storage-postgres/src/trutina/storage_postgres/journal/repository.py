"""Concrete JournalRepo implementation backed by PostgreSQL.

Implements the JournalRepo persistence contract using SQLAlchemy async
sessions. Contains no business rules -- account-reference validation and
balance checking are enforced upstream, before a JournalEntry ever
reaches this repository. This module's only responsibilities are
mapping between JournalEntry/JournalLine domain objects and
JournalEntryModel/JournalLineModel rows, and translating storage-level
failures into AppError.

Journal number allocation is a direct call against the sequence backing
journal_entries.journal_number's IDENTITY column, not a placeholder-row
insert. A sequence advance in PostgreSQL is not undone by a rolled-back
transaction, so a number returned by next_journal_number() can never be
reused even if the caller never calls save() for it -- the same
gap-tolerant guarantee an IDENTITY column already provides on its own.
"""

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.core.journal.repo import JournalRepo
from trutina.core.journal.schemas.journal import JournalEntry
from trutina.core.journal.schemas.line import JournalLine
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.shared.execution import PostgresExecutor

from .model import JournalEntryModel, JournalLineModel


class PostgresJournalRepo(JournalRepo):
    """JournalRepo implementation backed by PostgreSQL tables.

    journal_entries and journal_lines are written together, in one
    transaction per save() call, using explicit inserts rather than an
    ORM relationship() -- each JournalLine is mapped to its own
    JournalLineModel row with an explicit line_index recording its
    original position.

    Attributes:
        _session_factory: Produces a new AsyncSession bound to the
            configured engine, one per operation.
        _executor: Routes every database operation through
            translate_postgres_errors().
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        executor: PostgresExecutor,
    ) -> None:
        """Initialize the repository with its session factory and executor.

        Args:
            session_factory: Bound to an already-verified engine.
            executor: Wraps every operation this repository performs.
        """
        self._session_factory = session_factory
        self._executor = executor

    async def save(self, entry: JournalEntry) -> None:
        """Persist a journal entry and its lines in a single transaction.

        Args:
            entry: A fully validated domain JournalEntry, carrying a
                journal_number previously obtained from
                next_journal_number().

        Raises:
            AppError: If journal_number is already in use by a
                persisted entry (see class module docstring for the
                open flag on which ErrorCode this currently maps to).
                STORAGE_UNAVAILABLE/STORAGE_TIMEOUT for infrastructure
                failures.
        """

        async def _save() -> None:
            async with self._session_factory() as session:
                session.add(
                    JournalEntryModel(
                        journal_number=entry.journal_number,
                        posting_date=entry.posting_date,
                        description=entry.description,
                    )
                )
                for index, line in enumerate(entry.lines):
                    session.add(
                        JournalLineModel(
                            journal_number=entry.journal_number,
                            line_index=index,
                            account=line.account,
                            debit_amount=line.debit_amount,
                            credit_amount=line.credit_amount,
                        )
                    )
                await session.commit()

        try:
            await self._executor.run(_save())
        except IntegrityError as exc:
            raise self._on_duplicate(exc, entry.journal_number) from exc

    async def get_by_number(self, journal_number: int) -> JournalEntry | None:
        """Fetch a single journal entry with its lines, by journal number.

        Args:
            journal_number: The journal number to look up.

        Returns:
            The matching JournalEntry, with lines in their original
            saved order, or None if no entry has that number.
        """

        async def _get() -> tuple[JournalEntryModel, list[JournalLineModel]] | None:
            async with self._session_factory() as session:
                entry_result = await session.execute(
                    select(JournalEntryModel).where(
                        JournalEntryModel.journal_number == journal_number
                    )
                )
                entry_row = entry_result.scalar_one_or_none()
                if entry_row is None:
                    return None

                lines_result = await session.execute(
                    select(JournalLineModel)
                    .where(JournalLineModel.journal_number == journal_number)
                    .order_by(JournalLineModel.line_index)
                )
                return entry_row, list(lines_result.scalars().all())

        result = await self._executor.run(_get())
        if result is None:
            return None

        entry_row, line_rows = result
        return self._to_domain(entry_row, line_rows)

    async def list_entries(self) -> list[JournalEntry]:
        """Return every persisted journal entry, ordered by journal number.

        Returns:
            All journal entries, each with its lines in original saved
            order, ordered ascending by journal_number.
        """

        async def _list() -> tuple[list[JournalEntryModel], list[JournalLineModel]]:
            async with self._session_factory() as session:
                entries_result = await session.execute(
                    select(JournalEntryModel).order_by(JournalEntryModel.journal_number)
                )
                entry_rows = list(entries_result.scalars().all())

                lines_result = await session.execute(
                    select(JournalLineModel).order_by(
                        JournalLineModel.journal_number, JournalLineModel.line_index
                    )
                )
                line_rows = list(lines_result.scalars().all())

                return entry_rows, line_rows

        entry_rows, line_rows = await self._executor.run(_list())

        lines_by_journal: dict[int, list[JournalLineModel]] = {}
        for line in line_rows:
            lines_by_journal.setdefault(line.journal_number, []).append(line)

        return [
            self._to_domain(entry, lines_by_journal.get(entry.journal_number, []))
            for entry in entry_rows
        ]

    async def next_journal_number(self) -> int:
        """Reserve the next journal number.

        Advances journal_entries.journal_number's backing sequence
        directly, without inserting a row. The returned value is
        permanently consumed regardless of whether a subsequent save()
        call ever happens for it, since a PostgreSQL sequence advance is
        not affected by transaction rollback.

        Returns:
            A positive integer not yet used by any persisted entry.
        """

        async def _next() -> int:
            async with self._session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT nextval(pg_get_serial_sequence("
                        "'journal_entries', 'journal_number'))"
                    )
                )
                return result.scalar_one()

        return await self._executor.run(_next())

    @staticmethod
    def _on_duplicate(exc: IntegrityError, journal_number: int) -> AppError:
        """Translate a journal_number collision into an AppError.

        No ErrorCode member currently exists for this specific failure
        (flagged as an open item -- see module docstring). This path is
        expected to be unreachable in normal operation, since every
        caller obtains journal_number from next_journal_number() first.

        Args:
            exc: The IntegrityError raised by the failed insert.
            journal_number: The journal number that collided.

        Returns:
            An AppError.conflict() carrying the colliding value.
        """
        return AppError.conflict(
            code=ErrorCode.UNKNOWN_ERROR,
            resource="journal_entry",
            field_name="journal_number",
            value=str(journal_number),
        )

    @staticmethod
    def _to_domain(
        entry: JournalEntryModel, lines: list[JournalLineModel]
    ) -> JournalEntry:
        """Reconstruct a validated JournalEntry from persisted rows.

        Constructs a real JournalEntry, so every invariant it enforces
        (balance, line count, date range) is re-checked on every read.

        Args:
            entry: The persisted journal_entries row.
            lines: The persisted journal_lines rows for this entry,
                already ordered by line_index.

        Returns:
            A validated JournalEntry domain object.
        """
        return JournalEntry(
            journal_number=entry.journal_number,
            posting_date=entry.posting_date,
            description=entry.description,
            lines=[
                JournalLine(
                    account=line.account,
                    debit_amount=line.debit_amount,
                    credit_amount=line.credit_amount,
                )
                for line in lines
            ],
        )
