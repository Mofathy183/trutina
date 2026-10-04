from uuid import uuid4

import pytest
from trutina.authentication import AccessState

from tests.fakes import FakeUserStatusChecker


@pytest.mark.unit
class TestFakeUserStatusChecker:
    async def test_unknown_user_is_inactive(self):
        state = await FakeUserStatusChecker().get_access_state(uuid4())

        assert state == AccessState(is_active=False)

    async def test_returns_the_configured_state(self):
        subject = uuid4()
        checker = FakeUserStatusChecker()
        checker.set_state(subject, AccessState(is_active=True))

        assert (await checker.get_access_state(subject)).is_active is True
