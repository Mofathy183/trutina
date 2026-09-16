"""Shared SQLAlchemy declarative base and common model building blocks.

Defines Base -- the single declarative registry every feature's model.py
(account, journal, posting) builds its tables on -- plus the naming
convention applied to it, a reusable Money column type for every
monetary field, and TimestampedMixin for created_at/updated_at.

A single shared Base is a structural requirement, not a style choice:
SQLAlchemy can only resolve the postings/journal_lines -> journal_entries
foreign key when every table's Column objects are registered against the
same MetaData object, and Alembic's autogenerate diffs against exactly
one MetaData registry. No feature's model.py may declare its own
DeclarativeBase.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import DateTime, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Applied to every constraint/index created on Base.metadata. Without an
# explicit convention, Postgres assigns its own constraint names, which
# are neither stable across a drop/recreate cycle nor predictable enough
# for Alembic's autogenerate to diff reliably -- a renamed or recreated
# unique constraint would otherwise show up as "drop one, add another"
# with unrelated-looking names instead of a clean rename. This has to be
# set before the first table is defined; changing it later requires a
# migration for every existing constraint's name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every trutina-storage-postgres table.

    Every feature's model.py defines its table classes as subclasses of
    this Base and nothing else -- see the module docstring for why a
    second, independent DeclarativeBase anywhere in this package would
    silently break foreign-key resolution and Alembic autogenerate.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# A single source of truth for monetary-amount precision. Every feature
# that persists a debit/credit amount (journal_lines, postings) declares
# it as `Mapped[Money]` rather than hand-writing
# `mapped_column(Numeric(18, 2))` at each call site -- so a future
# precision change (e.g. numeric(18,2) -> numeric(19,4) for a
# multi-currency feature) is a one-line edit here, not an audit of every
# model file. This is also the thing that makes Trial Balance a plain
# `SUM(...) GROUP BY account`: numeric columns are natively aggregatable,
# unlike the decimal-as-string encoding the Mongo adapter uses.
Money = Annotated[Decimal, mapped_column(Numeric(18, 2), nullable=False)]


class TimestampedMixin:
    """Mixin providing created_at/updated_at columns on a table.

    Both columns are database-stamped via SQLAlchemy's server_default/
    onupdate, not set by application code before an insert. This matters
    specifically because it makes the columns correct regardless of
    which write path populates them -- a single ORM insert, a Core
    insert() statement, or a bulk-insert executed outside the ORM's
    unit-of-work all pass through the same server-side default, so there
    is no batch-write code path in this package that can leave either
    column unset by forgetting to call a hook.

    Attributes:
        created_at: Stamped once by Postgres at insert time
            (server_default=func.now()).
        updated_at: Stamped by Postgres at insert time and refreshed on
            every subsequent UPDATE (onupdate=func.now()).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
