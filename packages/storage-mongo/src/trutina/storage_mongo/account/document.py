"""Beanie document for the Account aggregate.

AccountDocument defines the MongoDB persistence representation of an
Account domain object. It intentionally performs no business validation;
all accounting rules and domain invariants have already been enforced by
the Account model before persistence.

Fields persisted
----------------
code      — Business identifier, independently unique.
name      — Canonical display name as validated by Account.validate_name().
name_key  — account_lookup_key(name), denormalized for case-insensitive
            uniqueness enforcement without requiring a collection collation.
            This field is an infrastructure-only implementation detail and
            is never exposed outside the persistence layer.
category  — AccountCategory enum, stored by Beanie as its string value
            via the built-in Enum encoder (no use_enum_values needed).

Fields NOT persisted
--------------------
normal_balance — Derived from category by the Account domain model.
                Persisting it would introduce a second source of truth
                that could diverge from the account category after future
                updates or migrations.

Identity strategy
-----------------
_id uses Beanie's default PydanticObjectId. It is an internal persistence
identifier only and never crosses the repository boundary. Domain models,
services, and repository contracts identify accounts exclusively by the
business code.

Enum serialization note
-----------------------
Beanie's built-in BSON encoder registers operator.attrgetter("value") for
all Enum types. AccountCategory members are therefore stored as their
string values ("ASSET", "LIABILITY", etc.) without requiring
use_enum_values=True. That option is intentionally omitted because it
would replace AccountCategory instances with plain strings after model
construction, breaking enum identity checks.

Migration note
--------------
name_key is derived by account_lookup_key(). If that normalization logic
changes, persisted name_key values become stale and uniqueness guarantees
are no longer reliable. A migration must recompute every stored name_key
using the updated normalization logic before rebuilding the
uq_account_name_key index.
"""

from pymongo import ASCENDING, IndexModel
from trutina.core.account.schemas.account import AccountCategory
from trutina.infrastructure.mongo.shared import TimestampedDocument


class AccountDocument(TimestampedDocument):
    """MongoDB persistence model for a Chart of Accounts entry.

    AccountDocument defines how a validated Account domain object is
    represented in MongoDB. It forms the persistence boundary between the
    accounting domain and the underlying database while intentionally
    containing no business validation or accounting rules.

    Domain services and the rest of the application operate on Account
    and related DTOs. Beanie and MongoDB operate on AccountDocument
    instances.
    """

    code: str
    name: str
    name_key: str
    category: AccountCategory

    class Settings:
        """Configure MongoDB persistence for account documents.

        Stores account documents in the ``accounts`` collection and
        defines the database indexes required to enforce repository-level
        uniqueness guarantees. These indexes complement the domain
        model's validation by protecting against duplicate business
        identifiers during concurrent writes.
        """

        name = "accounts"
        indexes = [
            IndexModel(
                [("code", ASCENDING)],
                unique=True,
                name="uq_account_code",
            ),
            IndexModel(
                [("name_key", ASCENDING)],
                unique=True,
                name="uq_account_name_key",
            ),
        ]
