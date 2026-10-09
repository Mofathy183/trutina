import pytest
from trutina.api.shared.actor import PRE_AUTH_ACTOR
from trutina.shared.rule import is_non_blank_actor


@pytest.mark.unit
class TestPreAuthActor:
    def test_is_not_blank(self):
        assert is_non_blank_actor(PRE_AUTH_ACTOR)

    def test_marks_a_system_writer(self):
        assert PRE_AUTH_ACTOR.startswith("system:")
