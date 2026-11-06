"""Set up the Energy Planner integration."""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SERVICE_PLAN_APPLIANCE,
    SERVICE_PLAN_APPLIANCE_PROFILE,
    SERVICE_PLAN_BATTERY_CHARGE,
    SERVICE_REMOVE_APPLIANCE_PROFILE,
    SERVICE_SAVE_APPLIANCE_PROFILE,
)
from .coordinator import EnergyPlannerCoordinator
from .services import (
    PLAN_APPLIANCE_PROFILE_SCHEMA,
    PLAN_APPLIANCE_SCHEMA,
    PLAN_BATTERY_CHARGE_SCHEMA,
    REMOVE_APPLIANCE_PROFILE_SCHEMA,
    SAVE_APPLIANCE_PROFILE_SCHEMA,
    async_plan_appliance,
    async_plan_appliance_profile,
    async_plan_battery_charge,
    async_remove_appliance_profile,
    async_save_appliance_profile,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]
type EnergyPlannerConfigEntry = ConfigEntry[EnergyPlannerCoordinator]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Energy Planner services and the legacy card path."""
    del config
    # The card is now distributed as a separate Marketplace Dashboard package.
    # Keep this static path for users who explicitly configured the legacy
    # resource, but do not add it to every dashboard automatically. That lets
    # the standalone card update without an integration restart and avoids two
    # versions of the custom element competing in the frontend.
    card_path = Path(__file__).parent / "www" / "energy-planner-card.js"
    if not card_path.is_file():
        card_path = Path(__file__).parents[2] / "www" / "energy-planner-card.js"
    if card_path.is_file() and getattr(hass, "http", None) is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig("/energy_planner/energy-planner-card.js", str(card_path))]
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_APPLIANCE,
        partial(async_plan_appliance, hass),
        schema=PLAN_APPLIANCE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_BATTERY_CHARGE,
        partial(async_plan_battery_charge, hass),
        schema=PLAN_BATTERY_CHARGE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_APPLIANCE_PROFILE,
        partial(async_save_appliance_profile, hass),
        schema=SAVE_APPLIANCE_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_APPLIANCE_PROFILE,
        partial(async_remove_appliance_profile, hass),
        schema=REMOVE_APPLIANCE_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAN_APPLIANCE_PROFILE,
        partial(async_plan_appliance_profile, hass),
        schema=PLAN_APPLIANCE_PROFILE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> bool:
    """Set up Energy Planner from a config entry."""
    coordinator = EnergyPlannerCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_load_persisted_state()

    @callback
    def _async_handle_price_change(event: Event) -> None:
        """Refresh promptly when the configured price source changes."""
        hass.async_create_task(
            coordinator.async_request_refresh(),
            f"{DOMAIN}_refresh_{entry.entry_id}",
        )

    settings = coordinator._settings()
    tracked_entities = [
        entry.options.get(CONF_PRICE_ENTITY, entry.data[CONF_PRICE_ENTITY]),
        settings.get(CONF_BATTERY_SOC_ENTITY),
        settings.get(CONF_BATTERY_CAPACITY_ENTITY),
        settings.get(CONF_BATTERY_CHARGE_POWER_ENTITY),
        settings.get(CONF_BATTERY_DISCHARGE_POWER_ENTITY),
    ]
    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            [entity_id for entity_id in tracked_entities if entity_id],
            _async_handle_price_change,
        )
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ConfigEntryNotReady, UpdateFailed) as err:
        _LOGGER.warning(
            "Price source unavailable while setting up Energy Planner entry %s; "
            "the native entities will recover when the source refreshes: %s",
            entry.entry_id,
            err,
        )
    await coordinator.async_restore_scheduled_plans()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> bool:
    """Unload an Energy Planner config entry."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> None:
    """Reload an Energy Planner config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
