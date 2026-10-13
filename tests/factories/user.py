"""Factory for ``trutina.authentication.User`` instances in tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from trutina.authentication import User


def make_user(
    *,
    id: UUID | None = None,
    email: str = "ann@example.com",
    password_hash: str = "fake$password",
    is_active: bool = True,
    created_at: datetime | None = None,
) -> User:
    """Build a valid, already-normalized user.

    Defaults: a fresh random id, ``ann@example.com``, the hash the
    ``FakePasswordHasher`` produces for ``"password"``, active, and a
    creation time of 2025-01-01T00:00:00Z.
    """
    return User(
        id=id if id is not None else uuid4(),
        email=email,
        password_hash=password_hash,
        is_active=is_active,
        created_at=(
            created_at if created_at is not None else datetime(2025, 1, 1, tzinfo=UTC)
        ),
    )
