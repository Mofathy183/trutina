"""SQLAlchemy model for the `audit_events` table.

An append-only record of who changed what, written by a repository in
the same transaction as the change it records. It exists because a
hard delete leaves no row to carry attribution, so account writes are
recorded here instead of in a column.

There is no foreign key and no before/after payload. `entity_key` is
the business key of the changed record as a string (an account code),
so a delete can still be recorded after the row it names is gone.
`actor` is the opaque caller identifier core received, stored as given.
No `updated_at`: rows are never updated, so `TimestampedMixin` is not
used. `occurred_at` is stamped by the database.

Append-only is a convention enforced by this package's repositories,
not by the database. Nothing here stops a privileged role from
updating or deleting a row.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from trutina.storage_postgres.shared import Base


class AuditAction(StrEnum):
    """The kind of change an audit event records."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


_ACTION_CHECK_SQL = "action IN ({})".format(
    ", ".join(f"'{action.value}'" for action in AuditAction)
)


class AuditEventModel(Base):
    """Persistence row for one audited change.

    Attributes:
        id: bigint surrogate key. Internal only.
        entity: Logical type of the changed record, e.g. ``account``.
        entity_key: Business key of the changed record as a string.
        action: One of `AuditAction`'s values, constrained by a CHECK
            built from the enum so the table cannot drift from it.
        actor: Opaque identifier of the caller who performed the write.
            Not a foreign key.
        occurred_at: Stamped by PostgreSQL at insert time, so it is the
            start time of the enclosing transaction.
    """

    __tablename__ = "audit_events"
    __table_args__ = (CheckConstraint(_ACTION_CHECK_SQL, name="action"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
