"""SQLAlchemy models for the `journal_entries` and `journal_lines` tables.

Unlike `AccountModel`, `journal_number` is not a separate surrogate key
next to a business identifier -- it IS the primary key. This directly
replaces the hand-rolled `counters` collection: PostgreSQL's `IDENTITY`
gives atomic, gap-tolerant sequence allocation for free.

`journal_lines.account` is a denormalized text column, not a foreign
key to `accounts` -- see the locked migration decision: an FK with
`ON UPDATE CASCADE` would silently rewrite historical posting labels on
an account rename, falsifying the audit trail; no cascade would block
renaming any account with posting history. A posting is a snapshot of
the account label at the time it was recorded, not a live join.

`posting_date` is a naive (timezone-unaware) timestamp, not a
`timestamptz`. `JournalEntry.posting_date` in trutina-core is a plain
`datetime` with no timezone awareness of its own, and its own
`validate_posting_date()` compares against a naive `datetime.now()`.
Storing this column as `timestamptz` would hand back a timezone-aware
value on read (asyncpg's own conversion behavior), which would then
fail that comparison with a TypeError the moment it round-tripped
through a real connection -- naive storage keeps this table's values
exactly what trutina-core already assumes they are, with no session-
timezone-dependent conversion happening anywhere in between.

No `relationship()` is declared between these two models. Repositories
in this package do explicit `_to_domain()`/`_to_row()` mapping instead.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from trutina.storage_postgres.shared import Base, TimestampedMixin


class JournalEntryModel(TimestampedMixin, Base):
    """Persistence row for one journal entry.

    Attributes:
        journal_number: bigint IDENTITY primary key. Not a surrogate --
            this is the same journal number `trutina-core` assigns via
            `JournalRepo.next_journal_number()` and the one identifier
            this table exposes externally.
        posting_date: When the entry was posted. Naive timestamp -- see
            module docstring for why. Constrained to be later than
            2020-01-01 and not in the future, mirroring `JournalEntry`'s
            own domain validator.
        description: Optional free-text description of the entry.
    """

    __tablename__ = "journal_entries"
    __table_args__ = (
        CheckConstraint(
            "posting_date > '2020-01-01' AND posting_date <= now()",
            name="posting_date_range",
        ),
    )

    journal_number: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    posting_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalLineModel(TimestampedMixin, Base):
    """Persistence row for one line of a journal entry.

    Attributes:
        id: bigint IDENTITY surrogate key. Internal only -- a line is
            addressed by (`journal_number`, `line_index`), never by
            this column, past this package's own boundary.
        journal_number: References the owning entry. `RESTRICT` on
            delete -- safe because journal entries are immutable and
            never renamed, so this FK carries no audit-trail risk the
            way an account-name FK would.
        line_index: Position of this line within its journal entry.
            Unique per (`journal_number`, `line_index`).
        account: Denormalized account display name -- see module
            docstring for why this is not a foreign key.
        debit_amount: Non-negative; exactly one of debit/credit is
            positive for any given line -- see
            `ck_journal_lines_exactly_one_side` below.
        credit_amount: Non-negative; see `debit_amount`.
    """

    __tablename__ = "journal_lines"
    __table_args__ = (
        UniqueConstraint(
            "journal_number",
            "line_index",
            name="uq_journal_lines_journal_number_line_index",
        ),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="exactly_one_side",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    journal_number: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("journal_entries.journal_number", ondelete="RESTRICT"),
        nullable=False,
    )
    line_index: Mapped[int] = mapped_column(Integer, nullable=False)
    account: Mapped[str] = mapped_column(Text, nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default="0"
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default="0"
    )
