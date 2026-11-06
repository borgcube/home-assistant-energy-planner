"""Regression tests for Home Assistant entry setup behavior."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _integration_module():
    """Load the integration package under its test-only module name."""
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
    return sys.modules[integration_name]


def test_entry_setup_forwards_entities_when_price_source_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing source must not hide the native entities during startup."""
    integration = _integration_module()
    from homeassistant.exceptions import ConfigEntryNotReady

    forwarded: list[tuple[object, list[object]]] = []
    restored = False

    class FakeCoordinator:
        def __init__(self, hass, entry) -> None:
            del hass, entry

        async def async_load_persisted_state(self) -> None:
            return None

        def _settings(self) -> dict[str, str]:
            return {}

        async def async_config_entry_first_refresh(self) -> None:
            raise ConfigEntryNotReady

        async def async_restore_scheduled_plans(self) -> None:
            nonlocal restored
            restored = True

    class FakeConfigEntries:
        async def async_forward_entry_setups(self, entry, platforms) -> None:
            forwarded.append((entry, platforms))

    entry = SimpleNamespace(
        entry_id="entry-id",
        options={},
        data={"price_entity": "sensor.missing"},
        runtime_data=None,
        async_on_unload=lambda callback: None,
    )
    hass = SimpleNamespace(config_entries=FakeConfigEntries())

    monkeypatch.setattr(integration, "EnergyPlannerCoordinator", FakeCoordinator)
    monkeypatch.setattr(
        integration,
        "async_track_state_change_event",
        lambda hass, entities, callback: (hass, entities, callback),
    )

    result = asyncio.run(integration.async_setup_entry(hass, entry))

    assert result is True
    assert restored is True
    assert forwarded == [(entry, integration.PLATFORMS)]


def test_global_setup_keeps_legacy_path_without_auto_registering_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The standalone Marketplace card must not be shadowed by the legacy URL."""
    integration = _integration_module()
    from homeassistant.components import frontend

    registered_paths: list[object] = []
    registered_services: list[tuple[object, ...]] = []

    class FakeHTTP:
        async def async_register_static_paths(self, paths) -> None:
            registered_paths.extend(paths)

    class FakeServices:
        def async_register(self, *args, **kwargs) -> None:
            registered_services.append((*args, kwargs))

    hass = SimpleNamespace(http=FakeHTTP(), services=FakeServices())
    monkeypatch.setattr(
        frontend,
        "add_extra_js_url",
        lambda *args, **kwargs: pytest.fail(
            "the legacy card must not be auto-registered"
        ),
    )

    assert asyncio.run(integration.async_setup(hass, {})) is True
    assert len(registered_paths) == 1
    assert registered_paths[0].url_path == "/energy_planner/energy-planner-card.js"
    assert len(registered_services) == 5
