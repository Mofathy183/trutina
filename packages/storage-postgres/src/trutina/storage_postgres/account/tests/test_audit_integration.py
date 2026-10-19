"""Integration tests for the audit trail PostgresAccountRepo writes.

Reads `audit_events` with raw SQL, because the table has no domain
model and no repository read. Does not re-verify uniqueness or lookup
behavior, which test_repository_integration.py covers.

The rollback tests force the audit insert to violate
`ck_audit_events_action` by patching the module's `_audit_row`, so the
real database, not a mock, rejects the row.
"""

import pytest
from sqlalchemy import text
from trutina.shared.errors import AppError, ErrorCode
from trutina.storage_postgres.account import repository as repository_module
from trutina.storage_postgres.audit import AuditEventModel

from tests.factories import TEST_ACTOR, make_account

OTHER_ACTOR = "system:other"


async def _audit_rows(engine) -> list[tuple[str, str, str, str]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT entity, entity_key, action, actor FROM audit_events ORDER BY id"
            )
        )
        return [tuple(row) for row in result.all()]


@pytest.fixture
def break_audit_row(monkeypatch):
    """Make the repository emit an audit row the CHECK constraint rejects."""

    def _bad_row(action, code, actor):
        return AuditEventModel(
            entity="account", entity_key=code, action="not-an-action", actor=actor
        )

    monkeypatch.setattr(repository_module, "_audit_row", _bad_row)


def _patch_bad_audit_row(monkeypatch) -> None:
    def _bad_row(action, code, actor):
        return AuditEventModel(
            entity="account", entity_key=code, action="not-an-action", actor=actor
        )

    monkeypatch.setattr(repository_module, "_audit_row", _bad_row)


@pytest.mark.integration
class TestAuditRowWritten:
    async def test_create_writes_one_audit_row(
        self, postgres_account_repo, postgres_connection
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )

        rows = await _audit_rows(postgres_connection.engine)

        assert rows == [("account", "1001", "create", TEST_ACTOR)]

    async def test_update_writes_one_audit_row_naming_the_updating_actor(
        self, postgres_account_repo, postgres_connection
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )

        await postgres_account_repo.update(
            make_account(code="1001", name="Main Cash"), created_by=OTHER_ACTOR
        )

        rows = await _audit_rows(postgres_connection.engine)
        assert rows == [
            ("account", "1001", "create", TEST_ACTOR),
            ("account", "1001", "update", OTHER_ACTOR),
        ]

    async def test_update_with_unchanged_values_still_writes_one_audit_row(
        self, postgres_account_repo, postgres_connection
    ):
        account = make_account(code="1001", name="Cash")
        await postgres_account_repo.create(account, created_by=TEST_ACTOR)

        await postgres_account_repo.update(account, created_by=TEST_ACTOR)

        rows = await _audit_rows(postgres_connection.engine)
        assert [row[2] for row in rows] == ["create", "update"]

    async def test_delete_writes_one_audit_row_and_removes_the_account(
        self, postgres_account_repo, postgres_connection
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )

        await postgres_account_repo.delete_by_code("1001", created_by=OTHER_ACTOR)

        rows = await _audit_rows(postgres_connection.engine)
        assert rows[-1] == ("account", "1001", "delete", OTHER_ACTOR)
        assert len(rows) == 2
        assert await postgres_account_repo.get_by_code("1001") is None

    async def test_occurred_at_is_stamped_with_a_timezone(
        self, postgres_account_repo, postgres_connection
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )

        async with postgres_connection.engine.connect() as conn:
            result = await conn.execute(text("SELECT occurred_at FROM audit_events"))
            occurred_at = result.scalar_one()

        assert occurred_at.tzinfo is not None


@pytest.mark.integration
class TestRejectedWritesLeaveNoAuditRow:
    async def test_duplicate_code_writes_no_second_audit_row(
        self, postgres_account_repo, postgres_connection
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )

        with pytest.raises(AppError):
            await postgres_account_repo.create(
                make_account(code="1001", name="Petty Cash"), created_by=TEST_ACTOR
            )

        assert len(await _audit_rows(postgres_connection.engine)) == 1

    async def test_updating_unknown_account_writes_no_audit_row(
        self, postgres_account_repo, postgres_connection
    ):
        with pytest.raises(AppError):
            await postgres_account_repo.update(
                make_account(code="9999"), created_by=TEST_ACTOR
            )

        assert await _audit_rows(postgres_connection.engine) == []

    async def test_deleting_unknown_account_writes_no_audit_row(
        self, postgres_account_repo, postgres_connection
    ):
        with pytest.raises(AppError):
            await postgres_account_repo.delete_by_code("9999", created_by=TEST_ACTOR)

        assert await _audit_rows(postgres_connection.engine) == []


@pytest.mark.integration
class TestFailedAuditInsertRollsBackTheWrite:
    async def test_create_is_rolled_back(
        self, postgres_account_repo, postgres_connection, break_audit_row
    ):
        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.create(
                make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
            )

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert await postgres_account_repo.get_by_code("1001") is None
        assert await _audit_rows(postgres_connection.engine) == []

    async def test_update_is_rolled_back(
        self, postgres_account_repo, postgres_connection, monkeypatch
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )
        rows_before = await _audit_rows(postgres_connection.engine)
        _patch_bad_audit_row(monkeypatch)

        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.update(
                make_account(code="1001", name="Main Cash"), created_by=TEST_ACTOR
            )

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        fetched = await postgres_account_repo.get_by_code("1001")
        assert fetched is not None
        assert fetched.name == "Cash"
        assert await _audit_rows(postgres_connection.engine) == rows_before

    async def test_delete_is_rolled_back(
        self, postgres_account_repo, postgres_connection, monkeypatch
    ):
        await postgres_account_repo.create(
            make_account(code="1001", name="Cash"), created_by=TEST_ACTOR
        )
        rows_before = await _audit_rows(postgres_connection.engine)
        _patch_bad_audit_row(monkeypatch)

        with pytest.raises(AppError) as exc_info:
            await postgres_account_repo.delete_by_code("1001", created_by=TEST_ACTOR)

        assert exc_info.value.code == ErrorCode.UNKNOWN_ERROR
        assert await postgres_account_repo.get_by_code("1001") is not None
        assert await _audit_rows(postgres_connection.engine) == rows_before
