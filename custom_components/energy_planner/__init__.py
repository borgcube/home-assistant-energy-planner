"""Set up the Energy Planner integration."""

from __future__ import annotations

import logging
from functools import partial

from homeassistant.config import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, SupportsResponse, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_PRICE_ENTITY,
    DOMAIN,
    SERVICE_PLAN_APPLIANCE,
    SERVICE_PLAN_BATTERY_CHARGE,
)
from .coordinator import EnergyPlannerCoordinator
from .services import (
    PLAN_APPLIANCE_SCHEMA,
    PLAN_BATTERY_CHARGE_SCHEMA,
    async_plan_appliance,
    async_plan_battery_charge,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]
type EnergyPlannerConfigEntry = ConfigEntry[EnergyPlannerCoordinator]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Energy Planner's read-only planning service."""
    del config
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
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> bool:
    """Set up Energy Planner from a config entry."""
    coordinator = EnergyPlannerCoordinator(hass, entry)
    entry.runtime_data = coordinator

    @callback
    def _async_handle_price_change(event: Event) -> None:
        """Refresh promptly when the configured price source changes."""
        hass.async_create_task(
            coordinator.async_request_refresh(),
            f"{DOMAIN}_refresh_{entry.entry_id}",
        )

    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            [entry.options.get(CONF_PRICE_ENTITY, entry.data[CONF_PRICE_ENTITY])],
            _async_handle_price_change,
        )
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.warning(
            "Price source unavailable while setting up Energy Planner entry %s; "
            "the native entities will recover when the source refreshes: %s",
            entry.entry_id,
            err,
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> bool:
    """Unload an Energy Planner config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: EnergyPlannerConfigEntry
) -> None:
    """Reload an Energy Planner config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
