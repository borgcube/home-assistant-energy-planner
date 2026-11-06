"""Tests for Home Assistant entities exposed by Energy Planner."""

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_fixed_monthly_cost_sensor_uses_options_and_keeps_monthly_scope() -> None:
    """The editable option is exposed as a separate monthly charge."""
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
    sensor_module = importlib.import_module(f"{integration_name}.sensor")
    FixedMonthlyCostSensor = sensor_module.FixedMonthlyCostSensor

    coordinator = SimpleNamespace(
        data=None,
        last_update_success=True,
        async_add_listener=lambda listener: (lambda: None),
    )
    entry = SimpleNamespace(
        entry_id="test-entry",
        options={"fixed_monthly_cost": 31.5},
        data={
            "fixed_monthly_cost": 27.98,
            "price_entity": "sensor.source",
        },
    )

    sensor = FixedMonthlyCostSensor(coordinator, entry)
    attributes = sensor.extra_state_attributes

    assert sensor.native_value == pytest.approx(31.5)
    assert attributes["billing_period"] == "month"
    assert attributes["model_status"] == "price_only"
    assert attributes["source_entity"] == "sensor.source"
    assert "last_updated" in attributes


def test_last_plan_sensor_exposes_latest_plan_in_native_ui() -> None:
    """The latest plan is visible after the action response is dismissed."""
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
    sensor_module = importlib.import_module(f"{integration_name}.sensor")
    LastPlanSensor = sensor_module.LastPlanSensor

    coordinator = SimpleNamespace(
        data=None,
        last_update_success=True,
        last_plan={
            "status": "recommended",
            "plan_type": "battery_charge",
            "target_energy_kwh": 3.75,
            "execution_mode": "plan_only",
            "resolution_minutes": 15,
        },
        async_add_listener=lambda listener: (lambda: None),
    )
    entry = SimpleNamespace(entry_id="test-entry")

    sensor = LastPlanSensor(coordinator, entry)

    assert sensor.native_value == "recommended"
    assert sensor.extra_state_attributes["plan_type"] == "battery_charge"
    assert sensor.extra_state_attributes["target_energy_kwh"] == pytest.approx(3.75)
    assert sensor.extra_state_attributes["resolution_minutes"] == 15


def test_adjusted_price_sensor_is_safe_before_price_data_arrives() -> None:
    """A transient source outage keeps the entity visible and unavailable."""
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
    sensor_module = importlib.import_module(f"{integration_name}.sensor")
    AdjustedPriceTimelineSensor = sensor_module.AdjustedPriceTimelineSensor

    coordinator = SimpleNamespace(
        data=None,
        last_update_success=False,
        async_add_listener=lambda listener: (lambda: None),
    )
    entry = SimpleNamespace(
        entry_id="test-entry",
        options={},
        data={
            "fixed_monthly_cost": 27.98,
            "price_entity": "sensor.source",
        },
    )

    sensor = AdjustedPriceTimelineSensor(coordinator, entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes["data"] == []
    assert sensor.extra_state_attributes["resolution_minutes"] is None
