from datetime import datetime

import pytest
from trutina.api.features.trial_balance.mapper import to_as_of_date


@pytest.mark.unit
class TestToAsOfDate:
    def test_returns_value_unchanged(self):
        dt = datetime(2025, 1, 1)

        assert to_as_of_date(dt) == dt

    def test_returns_none_unchanged(self):
        assert to_as_of_date(None) is None
