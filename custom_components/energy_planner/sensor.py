"""Sensors exposed by the Energy Planner integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EnergyPlannerConfigEntry
from .const import (
    ATTR_CURRENT_ALL_IN_PRICE,
    ATTR_CURRENT_SPOT_PRICE,
    ATTR_DATA,
    ATTR_FIXED_MONTHLY_COST,
    ATTR_LAST_UPDATED,
    ATTR_MODEL_STATUS,
    ATTR_SOURCE_ENTITY,
    CONF_FIXED_MONTHLY_COST,
    CONF_PRICE_ENTITY,
    DOMAIN,
    MODEL_STATUS_PRICE_ONLY,
    PLANNER_NAME,
)
from .coordinator import EnergyPlannerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyPlannerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Planner sensors."""
    async_add_entities([AdjustedPriceTimelineSensor(entry.runtime_data, entry)])


class AdjustedPriceTimelineSensor(
    CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity
):
    """Expose the adjusted price timeline in a card-compatible data attribute."""

    _attr_has_entity_name = True
    _attr_name = "Adjusted electricity price"
    _attr_native_unit_of_measurement = f"EUR/{UnitOfEnergy.KILO_WATT_HOUR}"
    _attr_icon = "mdi:currency-eur"
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the adjusted price sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_adjusted_price_timeline"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current all-in price where the source covers now."""
        point = self.coordinator.data.current
        return point.price_per_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose normalized hourly data for the planner and Lovelace card."""
        current = self.coordinator.data.current
        source_entity = self._entry.options.get(
            CONF_PRICE_ENTITY, self._entry.data[CONF_PRICE_ENTITY]
        )
        fixed_cost = float(
            self._entry.options.get(
                CONF_FIXED_MONTHLY_COST,
                self._entry.data[CONF_FIXED_MONTHLY_COST],
            )
        )
        return {
            ATTR_DATA: [point.as_dict() for point in self.coordinator.data.points],
            ATTR_CURRENT_ALL_IN_PRICE: current.price_per_kwh if current else None,
            ATTR_CURRENT_SPOT_PRICE: current.spot_price_per_kwh if current else None,
            ATTR_FIXED_MONTHLY_COST: fixed_cost,
            ATTR_LAST_UPDATED: datetime.now().astimezone().isoformat(),
            ATTR_MODEL_STATUS: MODEL_STATUS_PRICE_ONLY,
            ATTR_SOURCE_ENTITY: source_entity,
            "source_format": self.coordinator.data.source_format,
        }
