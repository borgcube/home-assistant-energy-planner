"""Regression tests for the Home Assistant config flow schema."""

import pytest


def test_config_flow_schema_is_accepted_by_home_assistant() -> None:
    """The schema must construct without a selector validation error."""
    pytest.importorskip("homeassistant")

    from energy_planner.config_flow import _schema

    _schema()
