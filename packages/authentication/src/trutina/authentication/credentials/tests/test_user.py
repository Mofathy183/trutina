from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from trutina.authentication import User


def _user(
    *,
    id: UUID | None = None,
    email: str = "a@example.com",
    password_hash: str = "secret-hash",
    is_active: bool = True,
    created_at: datetime | None = None,
) -> User:
    return User(
        id=id if id is not None else uuid4(),
        email=email,
        password_hash=password_hash,
        is_active=is_active,
        created_at=(
            created_at if created_at is not None else datetime(2025, 1, 1, tzinfo=UTC)
        ),
    )


@pytest.mark.unit
class TestUser:
    def test_repr_hides_the_password_hash(self):
        assert "secret-hash" not in repr(_user())

    def test_rejects_a_naive_created_at(self):
        with pytest.raises(ValidationError):
            _user(created_at=datetime(2025, 1, 1))

    def test_is_frozen(self):
        with pytest.raises(ValidationError):
            _user().is_active = False  # ty: ignore[invalid-assignment]
