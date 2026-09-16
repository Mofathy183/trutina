from unittest.mock import MagicMock

import pytest
from trutina.cli.composition.context import CliContext
from trutina.shared.errors import AppError, ErrorCode

from tests.factories import make_fake_account_repo


@pytest.mark.unit
class TestCliContextConnectionCaching:
    async def test_connects_once_across_multiple_repo_accessors(
        self, monkeypatch, test_settings
    ):
        call_count = 0
        fake_connection = MagicMock()

        async def fake_connect(postgres_settings):
            nonlocal call_count
            call_count += 1
            return fake_connection

        monkeypatch.setattr("trutina.cli.composition.context.connect", fake_connect)

        context = CliContext(settings=test_settings)

        await context.get_account_repo()
        await context.get_journal_repo()
        await context.get_posting_repo()

        assert call_count == 1


@pytest.mark.unit
class TestCliContextServiceCaching:
    async def test_returns_same_account_service_instance(self, fake_cli_context):
        first = await fake_cli_context.get_account_service()
        second = await fake_cli_context.get_account_service()

        assert first is second

    async def test_returns_same_journal_service_instance(self, fake_cli_context):
        first = await fake_cli_context.get_journal_service()
        second = await fake_cli_context.get_journal_service()

        assert first is second

    async def test_returns_same_posting_service_instance(self, fake_cli_context):
        first = await fake_cli_context.get_posting_service()
        second = await fake_cli_context.get_posting_service()

        assert first is second


@pytest.mark.unit
class TestCliContextRepositoryOwnership:
    async def test_injected_repo_survives_aclose(self, test_settings):
        injected_repo = make_fake_account_repo()
        context = CliContext(settings=test_settings, account_repo=injected_repo)

        await context.aclose()

        assert await context.get_account_repo() is injected_repo

    async def test_context_owned_repo_is_rebuilt_after_aclose(
        self, monkeypatch, test_settings
    ):
        call_count = 0
        fake_connection = MagicMock()

        async def fake_connect(postgres_settings):
            nonlocal call_count
            call_count += 1
            return fake_connection

        async def fake_disconnect(connection):
            return None

        monkeypatch.setattr("trutina.cli.composition.context.connect", fake_connect)
        monkeypatch.setattr(
            "trutina.cli.composition.context.disconnect", fake_disconnect
        )

        context = CliContext(settings=test_settings)

        first_repo = await context.get_account_repo()
        await context.aclose()
        second_repo = await context.get_account_repo()

        assert call_count == 2
        assert first_repo is not second_repo


@pytest.mark.unit
class TestCliContextConnectionErrorPropagation:
    async def test_propagates_storage_timeout_from_connect(
        self, monkeypatch, test_settings
    ):
        cause = AppError.storage_timeout(cause=Exception("timed out"))

        async def fake_connect(postgres_settings):
            raise cause

        monkeypatch.setattr("trutina.cli.composition.context.connect", fake_connect)
        context = CliContext(settings=test_settings)

        with pytest.raises(AppError) as exc_info:
            await context.get_account_repo()

        assert exc_info.value is cause
        assert exc_info.value.code == ErrorCode.STORAGE_TIMEOUT

    async def test_propagates_storage_unavailable_from_connect(
        self, monkeypatch, test_settings
    ):
        cause = AppError.storage_unavailable(cause=Exception("refused"))

        async def fake_connect(postgres_settings):
            raise cause

        monkeypatch.setattr("trutina.cli.composition.context.connect", fake_connect)
        context = CliContext(settings=test_settings)

        with pytest.raises(AppError) as exc_info:
            await context.get_account_repo()

        assert exc_info.value is cause
        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE
