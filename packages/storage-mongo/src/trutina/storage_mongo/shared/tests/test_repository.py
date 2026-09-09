import pytest
from pymongo.errors import ConnectionFailure
from trutina.infrastructure.mongo.shared import MongoExecutor
from trutina.shared.errors import AppError, ErrorCode


@pytest.mark.unit
class TestMongoExecutor:
    async def test_returns_coroutine_result(self):
        async def coro():
            return 42

        executor = MongoExecutor()

        result = await executor.run(coro())

        assert result == 42

    async def test_translates_mongo_errors(self):
        executor = MongoExecutor()
        cause = ConnectionFailure("connection refused")

        async def coro():
            raise cause

        with pytest.raises(AppError) as exc_info:
            await executor.run(coro())

        assert exc_info.value.code == ErrorCode.STORAGE_UNAVAILABLE
        assert exc_info.value.cause is cause
