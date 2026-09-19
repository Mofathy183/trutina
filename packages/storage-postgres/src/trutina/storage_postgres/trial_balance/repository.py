"""Concrete TrialBalanceRepo implementation backed by PostgreSQL.

Implements the read-only TrialBalanceRepo contract as a single
aggregation query over the existing `postings` table -- no new table,
no migration. Trial balance is a report, not a persisted resource: it
has nothing of its own to store, and everything it needs already lives
in `postings` (see trutina-storage-postgres's own posting/model.py for
that table's shape).

Grouping is done by `account_key`, not `account`, for the same reason
every other case-insensitive lookup in this package does -- two
postings recorded under differing casing of the same account name
(e.g. "Cash" and "cash") must aggregate into one row, not two. The
displayed `account` name for each group is picked deterministically
(the alphabetically-first spelling recorded against that key) via
MIN(account), since SQL aggregation requires every selected column to
be either grouped or aggregated.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trutina.core.trial_balance.repo import TrialBalanceRepo
from trutina.core.trial_balance.schemas.account_balance import AccountBalanceEntry
from trutina.storage_postgres.posting.model import PostingModel
from trutina.storage_postgres.shared.execution import PostgresExecutor


class PostgresTrialBalanceRepo(TrialBalanceRepo):
    """TrialBalanceRepo implementation backed by the postings table.

    Performs one GROUP BY aggregation query per call -- no writes, no
    new table, no migration. Every value returned is recomputed from
    postings on every call; nothing about a trial balance is cached or
    materialized, so it always reflects the current state of the
    ledger.

    Attributes:
        _session_factory: Produces a new AsyncSession bound to the
            configured engine, one per operation.
        _executor: Routes the aggregation query through
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
            executor: Wraps the aggregation query this repository runs.
        """
        self._session_factory = session_factory
        self._executor = executor

    async def get_account_balances(
        self,
        as_of_date: datetime | None = None,
    ) -> list[AccountBalanceEntry]:
        """Aggregate every posting's amounts, grouped by account.

        Args:
            as_of_date: Optional cutoff. When given, only postings with
                posting_date <= as_of_date are included in the
                aggregation. None means all-time -- no upper bound.

        Returns:
            One AccountBalanceEntry per account_key with at least one
            posting in scope, ordered ascending by the displayed
            account name. Empty list if no postings are in scope.
        """
        stmt = (
            select(
                func.min(PostingModel.account).label("account"),
                func.sum(PostingModel.debit_amount).label("debit_total"),
                func.sum(PostingModel.credit_amount).label("credit_total"),
            )
            .group_by(PostingModel.account_key)
            .order_by(func.min(PostingModel.account))
        )
        if as_of_date is not None:
            stmt = stmt.where(PostingModel.posting_date <= as_of_date)

        async def _get():
            async with self._session_factory() as session:
                result = await session.execute(stmt)
                return result.all()

        rows = await self._executor.run(_get())
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row) -> AccountBalanceEntry:
        """Build an AccountBalanceEntry from one aggregated result row.

        Extracted as its own pure function (no session, no I/O) so the
        row-to-domain mapping is unit-testable without a database --
        the same split PostgresPostingRepo._to_domain establishes for
        the posting adapter.

        Args:
            row: One row from the GROUP BY aggregation, exposing
                `account`, `debit_total`, and `credit_total` attributes
                (a SQLAlchemy Row in production; any object with those
                three attributes in a unit test).

        Returns:
            A validated AccountBalanceEntry. Construction re-runs
            AccountBalanceEntry's own field validation (account name
            normalization, non-negative totals), so a corrupted row
            surfaces as a Pydantic ValidationError here rather than
            silently propagating.
        """
        return AccountBalanceEntry(
            account=row.account,
            debit_total=row.debit_total,
            credit_total=row.credit_total,
        )
