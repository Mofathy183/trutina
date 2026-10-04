"""User model and persistence contract.

The model is minimal on purpose: the users milestone (M1b) designs the
final shape alongside its PostgreSQL adapter.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class User(BaseModel):
    """A person who can authenticate.

    Users are never hard-deleted; a user who must lose access is
    deactivated.

    Attributes:
        id: Stable subject identifier.
        email: Login identifier as entered. Lookups are case-insensitive.
        password_hash: Output of ``PasswordHasher.hash``; excluded from
            ``repr``.
        is_active: Whether the user may authenticate and write.
        created_at: Timezone-aware creation time.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str
    password_hash: str = Field(repr=False)
    is_active: bool
    created_at: AwareDatetime


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

        Args:
            user: The user to store.
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
        """
