"""User model and persistence contract.

The model is minimal on purpose: the final shape is designed alongside
the PostgreSQL adapter. Email is stored in one normalized form, so a
plain unique index is enough to enforce case-insensitive uniqueness.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .email import normalize_email


class User(BaseModel):
    """A person who can authenticate.

    Users are never hard-deleted; a user who must lose access is
    deactivated.

    Every constructed user carries a normalized email (trimmed and
    case-folded), so two addresses that differ only in case or
    surrounding whitespace are the same user on every code path. The
    address as originally typed is not kept.

    Attributes:
        id: Stable subject identifier.
        email: Normalized login identifier. See ``normalize_email``.
        password_hash: Output of ``PasswordHasher.hash``; excluded from
            ``repr``.
        is_active: Whether the user may authenticate and write.
        created_at: Timezone-aware creation time. Stamped by the
            database when the user is stored; a caller-supplied value
            is ignored by ``UserRepo.create``.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str
    password_hash: str = Field(repr=False)
    is_active: bool
    created_at: AwareDatetime

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        """Store every email in its canonical form.

        Normalizing at construction makes case-insensitive uniqueness
        hold on every path, so storage needs no second key column.
        """
        return normalize_email(value)


class UserRepo(ABC):
    """Persistence contract for users.

    Adapters must stay async, hold no business rules, and translate
    storage failures to ``AppError`` before they cross the boundary.
    Duplicate-email checking is the service's pre-check, with the
    storage unique index as the backstop.
    """

    @abstractmethod
    async def create(self, user: User) -> None:
        """Persist a new user.

        The storage layer stamps ``created_at``; the value on ``user``
        is ignored.

        Args:
            user: The user to store.

        Raises:
            AppError: DUPLICATE_USER_EMAIL if a user with the same
                normalized email exists. Its context never contains the
                email value.
        """

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        """Look up a user by id.

        Args:
            user_id: The subject identifier.

        Returns:
            The user, or ``None`` if none exists.
        """

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Look up a user by email, ignoring case.

        The argument is normalized with ``normalize_email`` before the
        lookup, so callers may pass the address as typed.

        Args:
            email: The email to look up.

        Returns:
            The user, or ``None`` if none exists.
        """

    @abstractmethod
    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        """Replace a user's stored password hash (rehash on login).

        Args:
            user_id: The user to update.
            password_hash: The new hash.

        Raises:
            AppError: UNKNOWN_USER if no user has this id.
        """

    @abstractmethod
    async def set_active(self, user_id: UUID, is_active: bool) -> None:
        """Activate or deactivate a user.

        Users are never hard-deleted, so this is how access is removed.

        Args:
            user_id: The user to update.
            is_active: The new access flag.

        Raises:
            AppError: UNKNOWN_USER if no user has this id.
        """
