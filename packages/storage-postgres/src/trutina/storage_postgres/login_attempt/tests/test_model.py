from typing import cast

import pytest
from sqlalchemy import Table
from trutina.storage_postgres.login_attempt import LoginAttemptModel
from trutina.storage_postgres.shared import Base


def _table() -> Table:
    return cast(Table, LoginAttemptModel.__table__)


@pytest.mark.unit
class TestLoginAttemptModelTable:
    def test_table_name_is_login_attempts(self):
        assert LoginAttemptModel.__tablename__ == "login_attempts"

    def test_shares_the_one_declarative_registry(self):
        assert LoginAttemptModel.metadata is Base.metadata

    def test_id_is_primary_key(self):
        assert _table().columns["id"].primary_key is True

    def test_has_no_foreign_keys(self):
        assert not _table().foreign_keys

    def test_has_no_updated_at_column(self):
        assert "updated_at" not in _table().columns


@pytest.mark.unit
class TestLoginAttemptModelColumns:
    @pytest.mark.parametrize("name", ["ip", "email_key", "attempted_at"])
    def test_column_is_not_nullable(self, name):
        assert _table().columns[name].nullable is False

    def test_attempted_at_is_timezone_aware(self):
        assert _table().columns["attempted_at"].type.timezone is True  # ty:ignore[unresolved-attribute]

    def test_attempted_at_is_supplied_by_the_caller(self):
        assert _table().columns["attempted_at"].server_default is None


@pytest.mark.unit
class TestLoginAttemptModelIndexes:
    def test_has_the_lookup_and_purge_indexes(self):
        columns = {tuple(c.name for c in i.columns) for i in _table().indexes}

        assert columns == {
            ("ip", "email_key", "attempted_at"),
            ("attempted_at",),
        }
