"""Tests for the Home Assistant plan-only service response."""

from datetime import datetime, timedelta

import pytest
from energy_planner.planning import AppliancePlanRequest, find_lowest_cost_window
from energy_planner.pricing import PricePoint, PriceTimeline


def test_plan_service_schema_and_response_are_read_only() -> None:
    """The service accepts hourly inputs and returns a plan-only response."""
    pytest.importorskip("homeassistant")
    from energy_planner.services import (
        PLAN_APPLIANCE_SCHEMA,
        _ensure_timezone,
        build_plan_response,
    )

    request_data = PLAN_APPLIANCE_SCHEMA(
        {
            "appliance_id": "dishwasher",
            "duration_minutes": "90",
            "deadline": "2026-11-06T04:00:00+01:00",
            "average_power_kw": "1.0",
        }
    )
    local_timezone = datetime.now().astimezone().tzinfo
    assert _ensure_timezone(
        datetime(2026, 11, 6, 4), local_timezone
    ).tzinfo == local_timezone
    timeline = PriceTimeline(
        points=(
            PricePoint(
                datetime.fromisoformat("2026-11-06T00:00:00+01:00"),
                datetime.fromisoformat("2026-11-06T01:00:00+01:00"),
                0.40,
                0.40,
            ),
            PricePoint(
                datetime.fromisoformat("2026-11-06T01:00:00+01:00"),
                datetime.fromisoformat("2026-11-06T02:00:00+01:00"),
                0.10,
                0.10,
            ),
            PricePoint(
                datetime.fromisoformat("2026-11-06T02:00:00+01:00"),
                datetime.fromisoformat("2026-11-06T03:00:00+01:00"),
                0.20,
                0.20,
            ),
        ),
        source_format="test",
    )
    request = AppliancePlanRequest(
        appliance_id=request_data["appliance_id"],
        duration=timedelta(minutes=request_data["duration_minutes"]),
        deadline=request_data["deadline"],
        average_power_kw=request_data["average_power_kw"],
        earliest_start=datetime.fromisoformat("2026-11-06T00:00:00+01:00"),
    )
    window = find_lowest_cost_window(timeline, request)

    response = build_plan_response(
        timeline, request, window, source_entity="sensor.source"
    )

    assert response["status"] == "recommended"
    assert response["execution_mode"] == "plan_only"
    assert response["start_time"] == "2026-11-06T01:00:00+01:00"
    assert response["end_time"] == "2026-11-06T02:30:00+01:00"
    assert response["estimated_cost"] == pytest.approx(0.20)
    assert response["resolution_minutes"] == 60


def test_plan_service_reports_unavailable_without_a_valid_window() -> None:
    """A missed deadline remains a safe plan-only result."""
    pytest.importorskip("homeassistant")
    from energy_planner.services import build_plan_response

    start = datetime.fromisoformat("2026-11-06T00:00:00+01:00")
    timeline = PriceTimeline(
        points=(PricePoint(start, start + timedelta(hours=1), 0.20, 0.20),),
        source_format="test",
    )
    request = AppliancePlanRequest(
        appliance_id="dishwasher",
        duration=timedelta(hours=2),
        deadline=start + timedelta(hours=1),
        average_power_kw=1.0,
        earliest_start=start,
    )

    response = build_plan_response(
        timeline, request, None, source_entity="sensor.source"
    )

    assert response["status"] == "unavailable"
    assert response["model_status"] == "unavailable"
    assert response["execution_mode"] == "plan_only"
    assert "start_time" not in response


def test_battery_plan_schema_and_response_are_price_only() -> None:
    """Battery charging remains a read-only plan with an energy estimate."""
    pytest.importorskip("homeassistant")
    from energy_planner.services import (
        PLAN_BATTERY_CHARGE_SCHEMA,
        build_plan_response,
    )

    request_data = PLAN_BATTERY_CHARGE_SCHEMA(
        {
            "duration_minutes": 90,
            "deadline": "2026-11-06T04:00:00+01:00",
            "charge_power_kw": 2.5,
        }
    )
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
    request = AppliancePlanRequest(
        appliance_id="battery_grid_charge",
        duration=timedelta(minutes=request_data["duration_minutes"]),
        deadline=request_data["deadline"],
        average_power_kw=request_data["charge_power_kw"],
        earliest_start=start,
    )
    window = find_lowest_cost_window(timeline, request)

    response = build_plan_response(
        timeline,
        request,
        window,
        source_entity="sensor.source",
        plan_type="battery_charge",
        target_energy_kwh=3.75,
    )

    assert response["plan_type"] == "battery_charge"
    assert response["target_energy_kwh"] == pytest.approx(3.75)
    assert response["execution_mode"] == "plan_only"
    assert response["model_status"] == "price_only"
    assert response["start_time"] == "2026-11-06T01:00:00+01:00"
    assert response["end_time"] == "2026-11-06T02:30:00+01:00"
