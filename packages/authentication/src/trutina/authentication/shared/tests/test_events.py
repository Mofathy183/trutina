import pytest
from trutina.authentication import AuthEvent, NoOpAuthEventSink


@pytest.mark.unit
class TestAuthEvent:
    def test_context_is_read_only(self):
        event = AuthEvent(name="auth.refresh_reused", context={"family": "f1"})

        with pytest.raises(TypeError):
            event.context["family"] = "other"  # ty: ignore[invalid-assignment]

    def test_context_is_copied_from_the_caller_mapping(self):
        source = {"family": "f1"}
        event = AuthEvent(name="auth.refresh_reused", context=source)

        source["family"] = "changed"

        assert event.context["family"] == "f1"


@pytest.mark.unit
class TestNoOpAuthEventSink:
    def test_accepts_an_event_without_raising(self):
        NoOpAuthEventSink().emit(AuthEvent(name="auth.x", context={}))
