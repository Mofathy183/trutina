"""SQLAlchemy model for the `postings` table.

Mirrors `journal_lines`' shape closely -- both represent one side of a
transaction against a denormalized account reference -- but persists the
ledger's permanent, immutable historical record rather than a journal
entry's editable-until-posted line.

`account` is denormalized text, not a foreign key, for the same reason
`journal_lines.account` is: a posting is a snapshot of the account label
at the moment it was recorded, and an FK with `ON UPDATE CASCADE` would
silently rewrite that snapshot on a later account rename.

`account_key` is a plain, non-computed column, set explicitly by the
repository via `account_lookup_key()`, for the same reason
`accounts.name_key` is.

`posting_date` is a naive (timezone-unaware) timestamp, not a
`timestamptz`, for the same reason `journal_entries.posting_date` is --
`LedgerPosting.posting_date` in trutina-core is a plain `datetime` with
no timezone awareness, and its own `validate_posting_date()` compares
against a naive `datetime.now()`. A `timestamptz` column would hand back
a timezone-aware value on read, which fails that comparison the moment
it round-trips through a real connection.

`UNIQUE (journal_number, line_index)` turns a successful duplicate-post
race -- two concurrent posting attempts for the same journal entry both
passing `PostingService`'s check-then-save pre-check before either
writes -- into a hard database failure instead of a silently duplicated
ledger.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from trutina.storage_postgres.shared import Base, TimestampedMixin


class PostingModel(TimestampedMixin, Base):
    """Persistence row for one immutable ledger posting.

    Attributes:
        id: bigint IDENTITY surrogate key. Internal only.
        account: Denormalized account display name at the time this
            posting was recorded -- see module docstring for why this
            is not a foreign key.
        account_key: Case-insensitive lookup key for `account`. Set
            explicitly by the repository via `account_lookup_key()` --
            never computed by the database. Indexed, not unique, since
            many postings legitimately share one account.
        debit_amount: Non-negative; exactly one of debit/credit is
            positive for any given posting -- see
            `ck_postings_exactly_one_side` below.
        credit_amount: Non-negative; see `debit_amount`.
        journal_number: References the owning entry. `RESTRICT` on
            delete -- journal entries are immutable and never renamed,
            so this FK carries no audit-trail risk.
        posting_date: When this posting was recorded. Naive timestamp --
            see module docstring for why. Constrained to be later than
            2020-01-01 and not in the future, mirroring `LedgerPosting`'s
            own domain validator.
        line_index: Position of the originating journal line this
            posting was derived from. Unique per
            (`journal_number`, `line_index`) -- see module docstring.
    """

    __tablename__ = "postings"
    __table_args__ = (
        UniqueConstraint(
            "journal_number",
            "line_index",
            name="uq_postings_journal_number_line_index",
        ),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) "
            "OR (credit_amount > 0 AND debit_amount = 0)",
            name="exactly_one_side",
        ),
        CheckConstraint(
            "posting_date > '2020-01-01' AND posting_date <= now()",
            name="posting_date_range",
        ),
        Index("ix_postings_account_key", "account_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account: Mapped[str] = mapped_column(Text, nullable=False)
    account_key: Mapped[str] = mapped_column(Text, nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default="0"
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default="0"
    )
    journal_number: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("journal_entries.journal_number", ondelete="RESTRICT"),
        nullable=False,
    )
    posting_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    line_index: Mapped[int] = mapped_column(Integer, nullable=False)
