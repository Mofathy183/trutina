"""SQLAlchemy model for the `accounts` table.

Maps Trutina's chart-of-accounts aggregate onto a single table. Contains
no business rules of its own — uniqueness, category validity, and normal
balance derivation all belong to `trutina-core`'s `Account` schema and
`AccountService`; this file only describes how an already-valid account
is stored.

`id` is a bigint IDENTITY surrogate key, internal to this table only.
It is never returned by any repository method, never appears in
`AccountViewModel`, and never crosses the `trutina-core` service
boundary — `code` is the account's business identifier and the only
one ever exposed to a caller, CLI or API alike.

`name_key` is a plain, non-computed unique column — NOT a Postgres
`GENERATED ... AS (lower(name))` column. It must be set explicitly by
the repository on every insert/update, using `trutina.shared.rule
.account_lookup_key()` — the exact same function `ChartOfAccounts`
uses for in-memory uniqueness. This is a deliberate choice: Postgres's
`lower()` and Python's `str.casefold()` (which `account_lookup_key()`
uses for Unicode-correct folding, e.g. German `ß` -> `ss`) are not
guaranteed to agree on every input. Having the database compute its
own version of the key would let the pre-check in `AccountService` and
the unique index that actually enforces uniqueness disagree on what
counts as a duplicate. Computing the key once, in Python, and writing
it explicitly removes that entire class of bug — mirroring how
`trutina-storage-mongo`'s `AccountDocument.name_key` already works,
since Mongo has no generated-column equivalent either.
"""

from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from trutina.core.account.schemas.account import AccountCategory
from trutina.storage_postgres.shared import Base, TimestampedMixin

_CATEGORY_VALUES = tuple(category.value for category in AccountCategory)
_CATEGORY_CHECK_SQL = "category IN ({})".format(
    ", ".join(f"'{value}'" for value in _CATEGORY_VALUES)
)


class AccountModel(TimestampedMixin, Base):
    """Persistence row for one chart-of-accounts entry.

    Attributes:
        id: bigint IDENTITY surrogate key. Internal only — never
            exposed past this package's own repository.
        code: The account's immutable business identifier. Unique.
        name: The account's display name, as most recently set by
            `AccountService.update_account()`. Mutable.
        name_key: Case-insensitive uniqueness key. Set explicitly by
            the repository via `account_lookup_key(name)` on every
            write — never computed by the database. See module
            docstring for why.
        category: One of `AccountCategory`'s values, constrained by a
            `CHECK` built from the enum itself so this table can never
            silently drift out of sync with `trutina-core`.
    """

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint(_CATEGORY_CHECK_SQL, name="category"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
