from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from trutina.authentication import User
from trutina.shared.errors import ErrorCode
from trutina.storage_postgres.identity.model import UserModel
from trutina.storage_postgres.identity.repository import PostgresUserRepo


class _FakeAsyncpgCause(Exception):
    def __init__(self, constraint_name: str | None) -> None:
        super().__init__("simulated asyncpg constraint violation")
        self.constraint_name = constraint_name


class _FakeOrigError(Exception):
    def __init__(self) -> None:
        super().__init__("simulated postgres constraint violation")


def _integrity_error(constraint_name: str | None) -> IntegrityError:
    orig = _FakeOrigError()
    orig.__cause__ = _FakeAsyncpgCause(constraint_name)
    return IntegrityError("stmt", {}, orig)


@pytest.mark.unit
class TestPostgresUserRepoToDomain:
    def test_reconstructs_user_from_row(self):
        user_id = uuid4()
        stamped = datetime(2026, 1, 1, tzinfo=UTC)
        model = UserModel(
            id=user_id,
            email="ann@example.com",
            password_hash="h",
            is_active=False,
            created_at=stamped,
        )

        user = PostgresUserRepo._to_domain(model)

        assert isinstance(user, User)
        assert user.id == user_id
        assert user.email == "ann@example.com"
        assert user.password_hash == "h"
        assert user.is_active is False
        assert user.created_at == stamped


@pytest.mark.unit
class TestPostgresUserRepoOnDuplicate:
    def test_maps_email_constraint_to_duplicate_user_email(self):
        error = PostgresUserRepo._on_duplicate(_integrity_error("uq_users_email"))

        assert error.code == ErrorCode.DUPLICATE_USER_EMAIL

    def test_context_names_the_field_but_never_the_value(self):
        error = PostgresUserRepo._on_duplicate(_integrity_error("uq_users_email"))

        assert dict(error.context) == {"resource": "user", "field": "email"}

    def test_maps_unrecognized_constraint_to_unknown_error(self):
        error = PostgresUserRepo._on_duplicate(_integrity_error("something_else"))

        assert error.code == ErrorCode.UNKNOWN_ERROR

    def test_maps_missing_constraint_name_to_unknown_error(self):
        error = PostgresUserRepo._on_duplicate(_integrity_error(None))

        assert error.code == ErrorCode.UNKNOWN_ERROR

    def test_unknown_error_preserves_the_cause(self):
        exc = _integrity_error("something_else")

        error = PostgresUserRepo._on_duplicate(exc)

        assert error.cause is exc
