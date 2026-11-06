"""Tests for price-source normalization and all-in cost calculation."""

from datetime import datetime

import pytest
from energy_planner.cost_models import FlatRateCostModel
from energy_planner.price_adapters import GenericHourlyPriceAdapter


def test_normalizes_price_timeline_data_attribute() -> None:
    """The card-compatible data format retains spot and adjusted prices."""
    spot_timeline = GenericHourlyPriceAdapter().normalize(
        {
            "data": [
                {"start_time": "2026-11-06T00:00:00+01:00", "price_per_kwh": 0.20},
                {"start_time": "2026-11-06T01:00:00+01:00", "price_per_kwh": 0.10},
            ]
        },
    )
    cost_model = FlatRateCostModel(0.02, 0.03, 27.98)
    point = spot_timeline.points[0]

    assert spot_timeline.source_format == "data"
    assert point.spot_price_per_kwh == 0.20
    assert cost_model.import_price(
        point.spot_price_per_kwh, point.start_time
    ) == pytest.approx(0.25)
    assert point.end_time == datetime.fromisoformat("2026-11-06T01:00:00+01:00")
    assert point.as_dict() == {
        "start_time": "2026-11-06T00:00:00+01:00",
        "end_time": "2026-11-06T01:00:00+01:00",
        "spot_price_per_kwh": 0.20,
        "price_per_kwh": 0.20,
    }


def test_normalizes_entso_style_hourly_prices() -> None:
    """Alternate hourly_prices/start/price attributes are accepted."""
    timeline = GenericHourlyPriceAdapter().normalize(
        {
            "hourly_prices": [
                {"start": "2026-11-06T00:00:00Z", "price": "0.19"},
            ]
        },
    )

    assert timeline.source_format == "hourly_prices"
    assert timeline.points[0].price_per_kwh == 0.19
    assert timeline.points[0].end_time == datetime.fromisoformat(
        "2026-11-06T01:00:00+00:00"
    )


def test_rejects_hourly_data_without_a_timezone() -> None:
    """Naive timestamps must not silently shift hourly schedules."""
    with pytest.raises(ValueError, match="timezone"):
        GenericHourlyPriceAdapter().normalize(
            {"prices": [{"datetime": "2026-11-06T00:00:00", "value": 0.20}]},
        )
