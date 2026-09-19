from datetime import datetime

import pytest
import typer
from trutina.cli.features.trial_balance.parser import parse_as_of_date


@pytest.mark.unit
class TestParseAsOfDate:
    def test_returns_parsed_datetime(self):
        assert parse_as_of_date("2025-01-31") == datetime(2025, 1, 31)

    def test_strips_surrounding_whitespace(self):
        assert parse_as_of_date("  2025-01-31  ") == datetime(2025, 1, 31)

    @pytest.mark.parametrize(
        "raw", ["not-a-date", "2025/01/31", "", "  ", "2025-13-01"]
    )
    def test_raises_bad_parameter_for_invalid_input(self, raw):
        with pytest.raises(typer.BadParameter) as exc_info:
            parse_as_of_date(raw)
        assert raw in str(exc_info.value)
