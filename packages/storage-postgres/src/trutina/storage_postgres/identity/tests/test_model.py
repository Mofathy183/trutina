from datetime import datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Table
from trutina.storage_postgres.identity.model import UserModel
from trutina.storage_postgres.shared import Base


def _table() -> Table:
    return cast(Table, UserModel.__table__)


@pytest.mark.unit
class TestUserModelTable:
    def test_table_name_is_users(self):
        assert UserModel.__tablename__ == "users"

    def test_shares_the_one_declarative_registry(self):
        assert UserModel.metadata is Base.metadata


@pytest.mark.unit
class TestUserModelColumns:
    def test_id_is_the_primary_key(self):
        assert _table().columns["id"].primary_key is True

    def test_id_is_a_uuid_supplied_by_the_application(self):
        column = _table().columns["id"]
        assert column.type.python_type is UUID
        assert column.server_default is None

    def test_email_is_not_nullable(self):
        assert _table().columns["email"].nullable is False

    def test_email_is_unique(self):
        assert _table().columns["email"].unique is True

    def test_there_is_no_separate_email_key_column(self):
        assert "email_key" not in _table().columns

    def test_password_hash_is_not_nullable(self):
        assert _table().columns["password_hash"].nullable is False

    def test_is_active_is_not_nullable_with_a_server_default(self):
        column = _table().columns["is_active"]
        assert column.nullable is False
        assert column.server_default is not None


@pytest.mark.unit
class TestUserModelTimestamps:
    def test_created_at_is_database_stamped(self):
        column = _table().columns["created_at"]
        assert column.type.python_type is datetime
        assert column.server_default is not None

    def test_updated_at_refreshes_on_update(self):
        assert _table().columns["updated_at"].onupdate is not None
