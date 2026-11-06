"""Tests for price-source normalization and all-in cost calculation."""

from datetime import datetime, timedelta

import pytest
from energy_planner.cost_models import FlatRateCostModel
from energy_planner.planning import (
    AppliancePlanRequest,
    find_lowest_cost_window,
    find_lowest_price_window,
)
from energy_planner.price_adapters import (
    EntsoDynamicPricesAdapter,
    GenericHourlyPriceAdapter,
)
from energy_planner.pricing import PricePoint, PriceTimeline


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


def test_normalizes_live_entso_dynamic_prices_shape() -> None:
    """The live ENTSO integration provides separate today and tomorrow lists."""
    timeline = EntsoDynamicPricesAdapter().normalize(
        {
            "prices_today": [
                {"time": "2026-11-06 23:00:00+01:00", "price": 0.44847},
            ],
            "prices_tomorrow": [
                {"time": "2026-11-07 00:00:00+01:00", "price": 0.45007},
                {"time": "2026-11-07 01:00:00+01:00", "price": 0.43582},
            ],
        }
    )

    assert timeline.source_format == "entso_dynamic_prices"
    assert len(timeline.points) == 3
    assert timeline.points[0].start_time == datetime.fromisoformat(
        "2026-11-06T23:00:00+01:00"
    )
    assert timeline.points[0].end_time == datetime.fromisoformat(
        "2026-11-07T00:00:00+01:00"
    )


def test_rejects_hourly_data_without_a_timezone() -> None:
    """Naive timestamps must not silently shift hourly schedules."""
    with pytest.raises(ValueError, match="timezone"):
        GenericHourlyPriceAdapter().normalize(
            {"prices": [{"datetime": "2026-11-06T00:00:00", "value": 0.20}]},
        )


def test_finds_the_cheapest_contiguous_window_before_deadline() -> None:
    """A multi-hour plan must use consecutive slots and respect its deadline."""
    start = datetime.fromisoformat("2026-11-06T00:00:00+01:00")
    timeline = PriceTimeline(
        points=(
            PricePoint(start, start + timedelta(hours=1), 0.40, 0.40),
            PricePoint(
                start + timedelta(hours=1), start + timedelta(hours=2), 0.10, 0.10
            ),
            PricePoint(
                start + timedelta(hours=2), start + timedelta(hours=3), 0.20, 0.20
            ),
            PricePoint(
                start + timedelta(hours=3), start + timedelta(hours=4), 0.50, 0.50
            ),
        ),
        source_format="test",
    )

    window = find_lowest_cost_window(
        timeline,
        AppliancePlanRequest(
            appliance_id="dishwasher",
            duration=timedelta(hours=2),
            deadline=start + timedelta(hours=4),
            average_power_kw=1.0,
        ),
    )

    assert window is not None
    assert window.start_time == start + timedelta(hours=1)
    assert window.end_time == start + timedelta(hours=3)
    assert window.estimated_cost == pytest.approx(0.30)


def test_returns_no_window_when_deadline_cannot_be_met() -> None:
    """A missed deadline must not produce an invalid automatic schedule."""
    start = datetime.fromisoformat("2026-11-06T00:00:00+01:00")
    timeline = PriceTimeline(
        points=(PricePoint(start, start + timedelta(hours=1), 0.20, 0.20),),
        source_format="test",
    )

    assert (
        find_lowest_cost_window(
            timeline,
            AppliancePlanRequest(
                appliance_id="dishwasher",
                duration=timedelta(hours=2),
                deadline=start + timedelta(hours=1),
                average_power_kw=1.0,
            ),
        )
        is None
    )


def test_finds_cheapest_future_price_window_without_an_appliance() -> None:
    """Price-only recommendations use the same contiguous-window planner."""
    start = datetime.fromisoformat("2026-11-06T00:00:00+01:00")
    timeline = PriceTimeline(
        points=(
            PricePoint(start, start + timedelta(hours=1), 0.40, 0.40),
            PricePoint(
                start + timedelta(hours=1), start + timedelta(hours=2), 0.10, 0.10
            ),
            PricePoint(
                start + timedelta(hours=2), start + timedelta(hours=3), 0.20, 0.20
            ),
        ),
        source_format="test",
    )

    window = find_lowest_price_window(
        timeline,
        duration=timedelta(hours=1),
        earliest_start=start,
        deadline=start + timedelta(hours=3),
    )

    assert window is not None
    assert window.start_time == start + timedelta(hours=1)
    assert window.end_time == start + timedelta(hours=2)
    assert window.average_price_per_kwh == pytest.approx(0.10)
