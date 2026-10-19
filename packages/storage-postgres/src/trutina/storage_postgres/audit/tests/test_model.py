from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table
from trutina.storage_postgres.audit import AuditAction, AuditEventModel
from trutina.storage_postgres.shared import Base


def _table() -> Table:
    return cast(Table, AuditEventModel.__table__)


@pytest.mark.unit
class TestAuditEventModelTable:
    def test_table_name_is_audit_events(self):
        assert AuditEventModel.__tablename__ == "audit_events"

    def test_shares_the_one_declarative_registry(self):
        assert AuditEventModel.metadata is Base.metadata

    def test_id_is_primary_key(self):
        assert _table().columns["id"].primary_key is True


@pytest.mark.unit
class TestAuditEventModelColumns:
    @pytest.mark.parametrize(
        "name", ["entity", "entity_key", "action", "actor", "occurred_at"]
    )
    def test_column_is_not_nullable(self, name):
        assert _table().columns[name].nullable is False

    def test_occurred_at_is_timezone_aware(self):
        assert _table().columns["occurred_at"].type.timezone is True  # ty:ignore[unresolved-attribute]

    def test_occurred_at_is_stamped_by_the_database(self):
        assert _table().columns["occurred_at"].server_default is not None

    def test_has_no_updated_at_column(self):
        assert "updated_at" not in _table().columns

    def test_has_no_foreign_keys(self):
        assert not _table().foreign_keys


@pytest.mark.unit
class TestAuditEventModelActionCheck:
    def _constraint(self) -> CheckConstraint:
        return next(
            c
            for c in _table().constraints
            if isinstance(c, CheckConstraint) and c.name == "ck_audit_events_action"
        )

    def test_check_constraint_exists_under_its_conventional_name(self):
        assert self._constraint() is not None

    def test_check_constraint_includes_every_action_value(self):
        sql_text = str(self._constraint().sqltext)
        for action in AuditAction:
            assert f"'{action.value}'" in sql_text
