import pytest
from trutina.observability.correlation import (
    correlation_scope,
    get_correlation_id,
    is_valid_correlation_id,
    new_correlation_id,
)


@pytest.mark.unit
class TestCorrelationScope:
    def test_binds_an_id_for_the_duration_of_the_scope(self):
        with correlation_scope() as cid:
            assert get_correlation_id() == cid

    def test_clears_the_id_on_exit(self):
        with correlation_scope():
            pass
        assert get_correlation_id() is None

    def test_reuses_a_valid_supplied_id(self):
        with correlation_scope("req-abc-123") as cid:
            assert cid == "req-abc-123"

    def test_replaces_an_invalid_supplied_id(self):
        with correlation_scope("has spaces/slash") as cid:
            assert cid != "has spaces/slash"

    def test_generates_a_new_id_when_none_supplied(self):
        with correlation_scope() as cid:
            assert cid
            assert is_valid_correlation_id(cid)

    def test_nested_scopes_restore_the_outer_id_on_exit(self):
        with correlation_scope("outer") as outer:
            with correlation_scope("inner") as inner:
                assert get_correlation_id() == inner
            assert get_correlation_id() == outer


@pytest.mark.unit
class TestIsValidCorrelationId:
    @pytest.mark.parametrize("value", ["abc-123", "REQ.ID_1", "a" * 64])
    def test_accepts_valid_ids(self, value):
        assert is_valid_correlation_id(value)

    @pytest.mark.parametrize("value", ["has space", "slash/here", "a" * 65, ""])
    def test_rejects_invalid_ids(self, value):
        assert not is_valid_correlation_id(value)


@pytest.mark.unit
class TestNewCorrelationId:
    def test_generates_a_valid_id(self):
        assert is_valid_correlation_id(new_correlation_id())

    def test_generates_distinct_ids(self):
        assert new_correlation_id() != new_correlation_id()
