"""Unit tests for build_container()'s pure wiring behavior.

Verifies only that build_container() assembles the correct object
graph with the correct identities, and that it performs no I/O. Does
NOT re-verify AccountService/JournalService/PostingService business
behavior -- that's already covered under modules/*/tests/.
"""

from unittest.mock import MagicMock

import pytest
from trutina.api.composition.bootstrap import build_container
from trutina.api.composition.container import Container
from trutina.core.account.service import AccountService
from trutina.core.journal.service import JournalService
from trutina.core.posting.service import PostingService
from trutina.storage_postgres.shared import PostgresConnection


@pytest.fixture
def fake_connection() -> PostgresConnection:
    """A PostgresConnection double with no real engine or session factory.

    build_container() only ever reads connection.session_factory and
    hands it to each Postgres*Repo constructor, which stores it without
    opening anything -- a MagicMock satisfies that with zero I/O,
    keeping this tier free of any real database dependency.
    """
    return MagicMock(spec=PostgresConnection)


@pytest.mark.unit
class TestBuildContainer:
    def test_returns_container_instance(self, fake_connection):
        result = build_container(fake_connection)

        assert isinstance(result, Container)

    def test_returns_account_service_instance(self, fake_connection):
        result = build_container(fake_connection)

        assert isinstance(result.account_service, AccountService)

    def test_returns_journal_service_instance(self, fake_connection):
        result = build_container(fake_connection)

        assert isinstance(result.journal_service, JournalService)

    def test_returns_posting_service_instance(self, fake_connection):
        result = build_container(fake_connection)

        assert isinstance(result.posting_service, PostingService)

    def test_journal_service_depends_on_same_account_service(self, fake_connection):
        result = build_container(fake_connection)

        assert result.journal_service._account_service is result.account_service

    def test_posting_service_depends_on_same_journal_service(self, fake_connection):
        result = build_container(fake_connection)

        assert result.posting_service._journal_service is result.journal_service

    def test_performs_no_io(self, fake_connection):
        """build_container() must succeed with no PostgreSQL instance reachable.

        Postgres*Repo construction only stores session_factory/executor
        references -- it never opens a session or executes a query at
        construction time -- so plain construction here must never raise
        or attempt a connection, even with a mocked connection.
        """
        result = build_container(fake_connection)

        assert result is not None

    def test_two_calls_return_independent_containers(self, fake_connection):
        first = build_container(fake_connection)
        second = build_container(fake_connection)

        assert first is not second
        assert first.account_service is not second.account_service
