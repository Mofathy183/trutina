from datetime import timedelta

import pytest
from trutina.authentication import AuthEvent

from tests.fakes import FakeAuthEventSink, FakeClock


@pytest.mark.unit
class TestFakeClock:
    def test_starts_aware_utc_and_does_not_move_alone(self):
        clock = FakeClock()

        assert clock.now().tzinfo is not None
        assert clock.now() == clock.now()

    def test_advance_moves_time_forward(self):
        clock = FakeClock()
        start = clock.now()

        clock.advance(timedelta(minutes=5))

        assert clock.now() == start + timedelta(minutes=5)


@pytest.mark.unit
class TestFakeAuthEventSink:
    def test_records_events_in_order(self):
        sink = FakeAuthEventSink()
        first, second = AuthEvent("a", {}), AuthEvent("b", {})

        sink.emit(first)
        sink.emit(second)

        assert sink.events == [first, second]
