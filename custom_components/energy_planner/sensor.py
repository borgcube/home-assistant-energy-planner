"""Sensors exposed by the Energy Planner integration."""

from __future__ import annotations

from datetime import datetime, timedelta
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
    ATTR_CURRENT_EXPORT_PRICE,
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
    MODEL_STATUS_UNAVAILABLE,
    PLANNER_NAME,
)
from .coordinator import EnergyPlannerCoordinator
from .planning import ScheduledWindow, find_lowest_price_window

PRICE_WINDOW_DURATION = timedelta(hours=1)
PRICE_WINDOW_HORIZON = timedelta(hours=24)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyPlannerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Planner sensors."""
    async_add_entities(
        [
            AdjustedPriceTimelineSensor(entry.runtime_data, entry),
            CheapestPriceWindowSensor(entry.runtime_data, entry),
            FixedMonthlyCostSensor(entry.runtime_data, entry),
            LastPlanSensor(entry.runtime_data, entry),
            PlanHistorySensor(entry.runtime_data, entry),
            ApplianceProfilesSensor(entry.runtime_data, entry),
            BatteryContextSensor(entry.runtime_data, entry),
            SolarForecastSensor(entry.runtime_data, entry),
        ]
    )


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
        timeline = self.coordinator.data
        point = timeline.current if timeline else None
        return point.price_per_kwh if point else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose normalized hourly data for the planner and Lovelace card."""
        timeline = self.coordinator.data
        current = timeline.current if timeline else None
        source_entity = self._entry.options.get(
            CONF_PRICE_ENTITY, self._entry.data[CONF_PRICE_ENTITY]
        )
        fixed_cost = float(
            self._entry.options.get(
                CONF_FIXED_MONTHLY_COST,
                self._entry.data[CONF_FIXED_MONTHLY_COST],
            )
        )
        export_price = None
        cost_model = getattr(self.coordinator, "cost_model", None)
        if current and cost_model is not None:
            export_fn = getattr(cost_model, "export_price", None)
            if export_fn is not None:
                export_price = export_fn(current.spot_price_per_kwh, current.start_time)
        return {
            ATTR_DATA: [point.as_dict() for point in timeline.points]
            if timeline
            else [],
            ATTR_CURRENT_ALL_IN_PRICE: current.price_per_kwh if current else None,
            ATTR_CURRENT_SPOT_PRICE: current.spot_price_per_kwh if current else None,
            ATTR_FIXED_MONTHLY_COST: fixed_cost,
            ATTR_LAST_UPDATED: datetime.now().astimezone().isoformat(),
            ATTR_MODEL_STATUS: getattr(
                self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
            ),
            ATTR_CURRENT_EXPORT_PRICE: export_price,
            ATTR_SOURCE_ENTITY: source_entity,
            "source_format": timeline.source_format if timeline else None,
            "resolution_minutes": timeline.resolution_minutes if timeline else None,
        }


class CheapestPriceWindowSensor(
    CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity
):
    """Expose the cheapest upcoming one-hour price-only recommendation."""

    _attr_has_entity_name = True
    _attr_name = "Cheapest 1-hour price window"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the price-window recommendation sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_cheapest_1h_window"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def _window(self) -> ScheduledWindow | None:
        """Return the cheapest complete future window in the next 24 hours."""
        timeline = self.coordinator.data
        if timeline is None:
            return None
        now = datetime.now().astimezone()
        return find_lowest_price_window(
            timeline,
            duration=PRICE_WINDOW_DURATION,
            earliest_start=now,
            deadline=now + PRICE_WINDOW_HORIZON,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the recommended window's start time."""
        window = self._window
        return window.start_time if window else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the recommendation without creating a device action."""
        window = self._window
        current = self.coordinator.data.current if self.coordinator.data else None
        source_entity = self._entry.options.get(
            CONF_PRICE_ENTITY, self._entry.data[CONF_PRICE_ENTITY]
        )
        if window is None:
            return {
                "model_status": MODEL_STATUS_UNAVAILABLE,
                "source_entity": source_entity,
                "source_format": (
                    self.coordinator.data.source_format
                    if self.coordinator.data
                    else None
                ),
                "resolution_minutes": (
                    self.coordinator.data.resolution_minutes
                    if self.coordinator.data
                    else None
                ),
                "reason": "No complete future price window is available",
            }

        return {
            "start_time": window.start_time.isoformat(),
            "end_time": window.end_time.isoformat(),
            "duration_hours": (window.end_time - window.start_time).total_seconds()
            / 3600,
            "average_price_per_kwh": window.average_price_per_kwh,
            "price_difference_vs_current_per_kwh": (
                current.price_per_kwh - window.average_price_per_kwh
                if current
                else None
            ),
            "horizon_hours": PRICE_WINDOW_HORIZON.total_seconds() / 3600,
            "model_status": getattr(
                self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
            ),
            "source_entity": source_entity,
            "source_format": self.coordinator.data.source_format,
            "resolution_minutes": self.coordinator.data.resolution_minutes,
            "last_updated": datetime.now().astimezone().isoformat(),
        }


class FixedMonthlyCostSensor(CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity):
    """Expose fixed electricity charges separately from hourly prices."""

    _attr_has_entity_name = True
    _attr_name = "Fixed monthly electricity cost"
    _attr_native_unit_of_measurement = "EUR"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:receipt-text-outline"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the fixed-cost sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_fixed_monthly_cost"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> float:
        """Return the configured recurring monthly cost."""
        return float(
            self._entry.options.get(
                CONF_FIXED_MONTHLY_COST,
                self._entry.data[CONF_FIXED_MONTHLY_COST],
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Describe the fixed charge without adding it to hourly prices."""
        source_entity = self._entry.options.get(
            CONF_PRICE_ENTITY, self._entry.data[CONF_PRICE_ENTITY]
        )
        return {
            "billing_period": "month",
            "model_status": getattr(
                self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
            ),
            "source_entity": source_entity,
            "last_updated": datetime.now().astimezone().isoformat(),
        }


class LastPlanSensor(CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity):
    """Expose the latest appliance or battery plan in the native UI."""

    _attr_has_entity_name = True
    _attr_name = "Last plan"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the latest-plan sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_plan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> str | None:
        """Return the latest plan status, or unknown before the first plan."""
        return (
            self.coordinator.last_plan.get("status")
            if self.coordinator.last_plan
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the complete latest plan response for cards and automations."""
        if self.coordinator.last_plan is None:
            return {
                "model_status": MODEL_STATUS_UNAVAILABLE,
                "execution_mode": "plan_only",
                "reason": "No plan has been requested yet",
            }
        return {
            **self.coordinator.last_plan,
            "last_plan_updated": datetime.now().astimezone().isoformat(),
        }


class PlanHistorySensor(CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity):
    """Expose recent persisted plans for dashboards and automations."""

    _attr_has_entity_name = True
    _attr_name = "Plan history"
    _attr_icon = "mdi:history"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the plan history sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_plan_history"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> int:
        """Return the number of retained plans."""
        return len(self.coordinator.plan_history)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a bounded, JSON-safe history for native cards."""
        return {
            "plans": self.coordinator.plan_history[:20],
            "retained_plan_count": len(self.coordinator.plan_history),
            "last_updated": datetime.now().astimezone().isoformat(),
        }


class ApplianceProfilesSensor(
    CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity
):
    """Expose saved appliance profiles in the native UI."""

    _attr_has_entity_name = True
    _attr_name = "Appliance profiles"
    _attr_icon = "mdi:chef-hat"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the profile sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_appliance_profiles"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> int:
        """Return the number of saved profiles."""
        return len(self.coordinator.profiles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return profile definitions without exposing credentials."""
        return {
            "profiles": {
                profile_id: profile.as_dict()
                for profile_id, profile in self.coordinator.profiles.items()
            },
            "last_updated": datetime.now().astimezone().isoformat(),
        }


class BatteryContextSensor(CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity):
    """Expose optional Enphase-compatible battery context."""

    _attr_has_entity_name = True
    _attr_name = "Battery context"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-medium"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the battery context sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery_context"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> float | None:
        """Return state of charge as a percentage."""
        snapshot = self.coordinator.battery_snapshot
        return snapshot.state_of_charge * 100 if snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose capacity and reserve context."""
        snapshot = self.coordinator.battery_snapshot
        if snapshot is None:
            return {
                "model_status": getattr(
                    self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
                ),
                "available": False,
            }
        return {
            "available": True,
            "usable_capacity_kwh": snapshot.usable_capacity_kwh,
            "reserve_percent": snapshot.reserve_percent,
            "charging_power_kw": snapshot.charging_power_kw,
            "discharging_power_kw": snapshot.discharging_power_kw,
            "captured_at": snapshot.captured_at.isoformat(),
            "model_status": getattr(
                self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
            ),
        }


class SolarForecastSensor(CoordinatorEntity[EnergyPlannerCoordinator], SensorEntity):
    """Expose optional Forecast.Solar energy context."""

    _attr_has_entity_name = True
    _attr_name = "Solar forecast"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the solar forecast sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_solar_forecast"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    def native_value(self) -> float | None:
        """Return forecast energy across the normalized response."""
        forecast = self.coordinator.solar_forecast
        return sum(point.energy_kwh for point in forecast.points) if forecast else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the normalized forecast intervals."""
        forecast = self.coordinator.solar_forecast
        return {
            "available": forecast is not None,
            "points": [
                {
                    "start_time": point.start_time.isoformat(),
                    "end_time": point.end_time.isoformat(),
                    "energy_kwh": point.energy_kwh,
                }
                for point in forecast.points
            ]
            if forecast
            else [],
            "model_status": getattr(
                self.coordinator, "model_status", MODEL_STATUS_PRICE_ONLY
            ),
        }
