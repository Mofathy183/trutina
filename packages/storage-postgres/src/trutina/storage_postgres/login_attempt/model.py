"""SQLAlchemy model for the `login_attempts` table.

One row per failed login, written by PostgresLoginAttemptRepo so the
authentication service can throttle repeated failures per client IP and
email together.

`email_key` is the attempted email in its normalized form
(`normalize_email()`: trimmed, case-folded), so differently cased
spellings of one address share one key. The attempted address need not
belong to any user, so there is no foreign key.

`attempted_at` is the caller-supplied, timezone-aware UTC time from
`Clock`, not a database default: the throttle window is computed from the
same clock, so a stored time can never disagree with it. No `updated_at`:
rows are only inserted and deleted, so `TimestampedMixin` is not used.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from trutina.storage_postgres.shared import Base


class LoginAttemptModel(Base):
    """Persistence row for one failed login.

    Attributes:
        id: bigint surrogate key. Internal only.
        ip: Client address as given ("unknown" when undetermined). Plain
            text, not `inet`, so that sentinel stays valid.
        email_key: Normalized attempted email.
        attempted_at: When the failure happened, aware UTC.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (
        # Serves count_failures and clear, which filter on all three.
        Index(
            "ix_login_attempts_ip_email_key_attempted_at",
            "ip",
            "email_key",
            "attempted_at",
        ),
        # Serves purge_before, which filters on time alone.
        Index("ix_login_attempts_attempted_at", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    email_key: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
