"""Concrete PostingRepo implementation backed by PostgreSQL.

Implements the PostingRepo persistence contract using SQLAlchemy async
sessions. Contains no business rules -- the one-posting-per-journal-entry
check is PostingService's responsibility, enforced there via a
check-then-save pre-check against get_by_journal_number(). This
repository's UNIQUE (journal_number, line_index) constraint exists
specifically as the database-level backstop for the race window that
pre-check cannot close on its own: two concurrent post attempts for the
same journal entry can both pass the pre-check before either writes, and
this constraint turns the second write into a hard failure instead of a
silently duplicated ledger.

account_key is a plain column, not a database-computed one -- like
accounts.name_key, it is produced here, once, via account_lookup_key(),
on every posting written, so it can never disagree with the
Unicode-correct case-folding rule the rest of the domain uses.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.core.posting.repo import PostingRepo
from trutina.core.posting.schemas.ledger_posting import LedgerPosting
from trutina.shared.errors import AppError, ErrorCode
from trutina.shared.rule import account_lookup_key
from trutina.storage_postgres.shared.execution import PostgresExecutor

from .model import PostingModel


class PostgresPostingRepo(PostingRepo):
    """PostingRepo implementation backed by a PostgreSQL postings table.

    save_many() writes an entire batch in one transaction, one commit --
    the real transactional guarantee the original Mongo adapter's
    single insert_many() (no ClientSession) never had.

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

    async def save_many(self, postings: list[LedgerPosting]) -> None:
        """Persist a batch of postings in a single transaction.

        All postings in the batch are assumed derived from one journal
        entry; line_index records each posting's original position
        within that entry, matching journal_lines' own convention.

        Args:
            postings: Fully validated LedgerPosting records, in the
                order they should be recorded.

        Raises:
            AppError: JOURNAL_ALREADY_POSTED if the batch collides with
                an already-persisted posting for the same journal number
                and line position -- the database-level backstop for the
                race PostingService's own pre-check cannot fully close.
                STORAGE_UNAVAILABLE/STORAGE_TIMEOUT for infrastructure
                failures.
        """

        async def _save_many() -> None:
            async with self._session_factory() as session:
                for index, posting in enumerate(postings):
                    session.add(
                        PostingModel(
                            account=posting.account,
                            account_key=account_lookup_key(posting.account),
                            debit_amount=posting.debit_amount,
                            credit_amount=posting.credit_amount,
                            journal_number=posting.journal_number,
                            posting_date=posting.posting_date,
                            line_index=index,
                        )
                    )
                await session.commit()

        try:
            await self._executor.run(_save_many())
        except IntegrityError as exc:
            raise self._on_duplicate(exc, postings) from exc

    async def get_by_account(self, account: str) -> list[LedgerPosting]:
        """Return all postings for a given account, ordered by posting date.

        Args:
            account: The account name to filter by, matched
                case-insensitively via account_lookup_key().

        Returns:
            All matching postings, ordered ascending by posting_date.
            Empty list if none exist.
        """
        key = account_lookup_key(account)

        async def _get() -> list[PostingModel]:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(PostingModel)
                    .where(PostingModel.account_key == key)
                    .order_by(PostingModel.posting_date)
                )
                return list[PostingModel](result.scalars().all())

        models = await self._executor.run(_get())
        return [self._to_domain(model) for model in models]

    async def get_by_journal_number(self, journal_number: int) -> list[LedgerPosting]:
        """Return all postings derived from a given journal entry.

        Args:
            journal_number: The journal entry number to filter by.

        Returns:
            All matching postings, in the order they were originally
            saved (by line_index). Empty list if none exist.
        """

        async def _get() -> list[PostingModel]:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(PostingModel)
                    .where(PostingModel.journal_number == journal_number)
                    .order_by(PostingModel.line_index)
                )
                return list[PostingModel](result.scalars().all())

        models = await self._executor.run(_get())
        return [self._to_domain(model) for model in models]

    @staticmethod
    def _on_duplicate(exc: IntegrityError, postings: list[LedgerPosting]) -> AppError:
        """Translate a (journal_number, line_index) collision into an AppError.

        Args:
            exc: The IntegrityError raised by the failed batch insert.
            postings: The batch that was being written, used only to
                recover the journal_number for the error context -- all
                postings in one batch share the same journal_number.

        Returns:
            AppError.conflict() with JOURNAL_ALREADY_POSTED, matching
            the code PostingService's own application-level pre-check
            already raises for this exact business condition.
        """
        journal_number = postings[0].journal_number if postings else None
        return AppError.conflict(
            code=ErrorCode.JOURNAL_ALREADY_POSTED,
            resource="journal_entry",
            field_name="journal_number",
            value=str(journal_number),
        )

    @staticmethod
    def _to_domain(model: PostingModel) -> LedgerPosting:
        """Reconstruct a validated LedgerPosting from a persisted row.

        Constructs a real, frozen LedgerPosting, so every invariant it
        enforces (single-sided amounts, date range, account validity) is
        re-checked on every read.

        Args:
            model: The persisted row.

        Returns:
            A validated LedgerPosting domain object.
        """
        return LedgerPosting(
            account=model.account,
            debit_amount=model.debit_amount,
            credit_amount=model.credit_amount,
            journal_number=model.journal_number,
            posting_date=model.posting_date,
        )
