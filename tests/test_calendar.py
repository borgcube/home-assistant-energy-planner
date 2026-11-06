"""Tests for the native Energy Planner plan calendar."""

import importlib
import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


def _calendar_module():
    """Load the integration package and return its calendar module."""
    pytest.importorskip("homeassistant")
    component_path = Path(__file__).parents[1] / "custom_components" / "energy_planner"
    integration_name = "energy_planner.integration"
    if integration_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            integration_name,
            component_path / "__init__.py",
            submodule_search_locations=[str(component_path)],
        )
        assert spec is not None and spec.loader is not None
        integration = importlib.util.module_from_spec(spec)
        sys.modules[integration_name] = integration
        spec.loader.exec_module(integration)
    return importlib.import_module(f"{integration_name}.calendar")


def test_plan_to_calendar_event_exposes_battery_window() -> None:
    """A recommended battery plan becomes a readable native event."""
    calendar_module = _calendar_module()
    start = datetime.fromisoformat("2026-11-07T11:00:00+01:00")
    end = start + timedelta(minutes=90)

    event = calendar_module.plan_to_calendar_event(
        {
            "status": "recommended",
            "plan_type": "battery_charge",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "target_energy_kwh": 3.75,
            "estimated_cost": 1.5628,
            "estimated_saving_vs_current": 0.2263,
            "execution_mode": "plan_only",
            "model_status": "price_only",
            "resolution_minutes": 15,
        },
        "test-entry",
    )

    assert event is not None
    assert event.summary == "Battery charge plan"
    assert event.start == start
    assert event.end == end
    assert event.uid == "test-entry-last-plan"
    assert "Target energy: 3.75 kWh" in (event.description or "")
    assert "Estimated cost: €1.56" in (event.description or "")
    assert "no device control" in (event.description or "")


def test_plan_to_calendar_event_ignores_unavailable_or_invalid_plans() -> None:
    """Unavailable and malformed responses never create calendar events."""
    calendar_module = _calendar_module()

    assert calendar_module.plan_to_calendar_event(None, "test-entry") is None
    assert (
        calendar_module.plan_to_calendar_event(
            {"status": "unavailable"}, "test-entry"
        )
        is None
    )
    assert (
        calendar_module.plan_to_calendar_event(
            {
                "status": "recommended",
                "start_time": "not-a-date",
                "end_time": "also-not-a-date",
            },
            "test-entry",
        )
        is None
    )


def test_plan_calendar_entity_uses_latest_coordinator_plan() -> None:
    """The native entity reflects the latest action response."""
    calendar_module = _calendar_module()
    start = datetime.fromisoformat("2026-11-07T11:00:00+01:00")
    coordinator = SimpleNamespace(
        last_plan={
            "status": "recommended",
            "appliance_id": "dishwasher",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
        },
        async_add_listener=lambda listener: (lambda: None),
    )
    entry = SimpleNamespace(entry_id="test-entry")

    calendar = calendar_module.EnergyPlannerCalendar(coordinator, entry)

    assert calendar.event is not None
    assert calendar.event.summary == "Appliance plan: dishwasher"
