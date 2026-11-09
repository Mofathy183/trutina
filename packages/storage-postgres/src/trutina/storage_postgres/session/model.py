"""SQLAlchemy model for the `sessions` table.

One row per session issued to an API or CLI client. The raw token is
never stored: `token_hash` holds the output of `SessionTokenHasher`, and
its unique constraint is also the lookup index.

Every time column is the caller-supplied, timezone-aware UTC value from
`Clock`, not a database default, because session expiry is computed from
the same clock and a stored time must never disagree with it. There is
no `updated_at`: `last_used_at`, `authenticated_at` and `revoked_at`
record the changes a session undergoes, so `TimestampedMixin` is not
used. The foreign key to `users.id` is RESTRICT: users are never
deleted, and a cascade would silently destroy rows that ADR 0002 keeps
for forensics.

Contains no policy. Lifetimes, when a touch is due and retention belong
to the session service, not to this table or its repository.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from trutina.authentication import ClientKind
from trutina.storage_postgres.shared import Base

_CLIENT_KIND_CHECK_SQL = "client_kind IN ({})".format(
    ", ".join(f"'{kind.value}'" for kind in ClientKind)
)


class SessionModel(Base):
    """Persistence row for one session.

    Attributes:
        id: bigint surrogate key. Internal only.
        token_hash: Hash of the session token. Unique; never the token.
        user_id: Owner. References `users.id` with RESTRICT.
        client_kind: One of `ClientKind`'s values, constrained by a CHECK
            built from the enum so the table cannot drift from it.
        created_at: When the session was created, aware UTC.
        last_used_at: When the session was last recorded as used.
        authenticated_at: When the user last proved their password in
            this session.
        idle_expires_at: Expiry if the session stays unused.
        absolute_expires_at: Expiry regardless of use. Fixed at creation.
        revoked_at: Set when the session was revoked; null while live.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(_CLIENT_KIND_CHECK_SQL, name="client_kind"),
        # Serves revoke_all_for_user, which filters on the owner alone.
        Index("ix_sessions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    client_kind: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    authenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
