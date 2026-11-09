from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table
from trutina.authentication import ClientKind
from trutina.storage_postgres.session import SessionModel
from trutina.storage_postgres.shared import Base

_REQUIRED_TIMES = [
    "created_at",
    "last_used_at",
    "authenticated_at",
    "idle_expires_at",
    "absolute_expires_at",
]


def _table() -> Table:
    return cast(Table, SessionModel.__table__)


@pytest.mark.unit
class TestSessionModelTable:
    def test_table_name_is_sessions(self):
        assert SessionModel.__tablename__ == "sessions"

    def test_shares_the_one_declarative_registry(self):
        assert SessionModel.metadata is Base.metadata

    def test_id_is_primary_key(self):
        assert _table().columns["id"].primary_key is True

    def test_has_no_updated_at_column(self):
        assert "updated_at" not in _table().columns


@pytest.mark.unit
class TestSessionModelColumns:
    def test_token_hash_is_unique_and_not_nullable(self):
        column = _table().columns["token_hash"]
        assert column.unique is True
        assert column.nullable is False

    def test_user_id_references_users_and_restricts_deletion(self):
        (fk,) = _table().columns["user_id"].foreign_keys
        assert fk.target_fullname == "users.id"
        assert fk.ondelete == "RESTRICT"

    @pytest.mark.parametrize("name", ["user_id", "client_kind", *_REQUIRED_TIMES])
    def test_column_is_not_nullable(self, name):
        assert _table().columns[name].nullable is False

    @pytest.mark.parametrize("name", [*_REQUIRED_TIMES, "revoked_at"])
    def test_time_column_is_timezone_aware(self, name):
        assert _table().columns[name].type.timezone is True

    @pytest.mark.parametrize("name", [*_REQUIRED_TIMES, "revoked_at"])
    def test_time_column_is_supplied_by_the_caller(self, name):
        assert _table().columns[name].server_default is None

    def test_revoked_at_is_nullable(self):
        assert _table().columns["revoked_at"].nullable is True


@pytest.mark.unit
class TestSessionModelConstraints:
    def _check(self) -> CheckConstraint:
        return next(
            c
            for c in _table().constraints
            if isinstance(c, CheckConstraint) and c.name == "ck_sessions_client_kind"
        )

    def test_client_kind_check_includes_every_kind(self):
        sql_text = str(self._check().sqltext)
        for kind in ClientKind:
            assert f"'{kind.value}'" in sql_text

    def test_has_only_the_owner_index(self):
        columns = {tuple(c.name for c in i.columns) for i in _table().indexes}

        assert columns == {("user_id",)}
