"""Regression tests for the Home Assistant config flow schema."""

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest


def test_config_flow_schema_is_accepted_by_home_assistant() -> None:
    """The schema must construct without a selector validation error."""
    pytest.importorskip("homeassistant")

    from energy_planner.config_flow import _schema

    _schema()


def test_integration_setup_accepts_home_assistant_config() -> None:
    """The integration setup hook matches Home Assistant's two-argument API."""
    pytest.importorskip("homeassistant")

    component_path = Path(__file__).parents[1] / "custom_components" / "energy_planner"
    module_name = "energy_planner.integration"
    spec = importlib.util.spec_from_file_location(
        module_name,
        component_path / "__init__.py",
        submodule_search_locations=[str(component_path)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    assert list(inspect.signature(module.async_setup).parameters) == ["hass", "config"]
