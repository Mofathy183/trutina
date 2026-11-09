from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from trutina.authentication import ClientKind
from trutina.shared.errors import ErrorCode
from trutina.storage_postgres.session.model import SessionModel
from trutina.storage_postgres.session.repository import PostgresSessionRepo

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


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
class TestPostgresSessionRepoOnIntegrityError:
    @pytest.mark.parametrize(
        "constraint", ["uq_sessions_token_hash", "fk_sessions_user_id_users"]
    )
    def test_names_the_violated_constraint(self, constraint):
        error = PostgresSessionRepo._on_integrity_error(_integrity_error(constraint))

        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert dict(error.context) == {
            "resource": "session",
            "constraint": constraint,
        }

    def test_reports_unknown_when_no_constraint_is_named(self):
        error = PostgresSessionRepo._on_integrity_error(_integrity_error(None))

        assert error.code == ErrorCode.UNKNOWN_ERROR
        assert error.context["constraint"] == "unknown"

    def test_never_attaches_the_driver_exception_as_cause(self):
        error = PostgresSessionRepo._on_integrity_error(
            _integrity_error("uq_sessions_token_hash")
        )

        assert error.cause is None


@pytest.mark.unit
class TestPostgresSessionRepoToRecord:
    def test_reconstructs_the_record_from_a_row(self):
        user_id = uuid4()
        model = SessionModel(
            token_hash="h1",
            user_id=user_id,
            client_kind="cli",
            created_at=NOW,
            last_used_at=NOW,
            authenticated_at=NOW,
            idle_expires_at=NOW + timedelta(days=14),
            absolute_expires_at=NOW + timedelta(days=30),
            revoked_at=None,
        )

        record = PostgresSessionRepo._to_record(model)

        assert record.token_hash == "h1"
        assert record.user_id == user_id
        assert record.client_kind is ClientKind.CLI
        assert record.idle_expires_at == NOW + timedelta(days=14)
        assert record.revoked_at is None
