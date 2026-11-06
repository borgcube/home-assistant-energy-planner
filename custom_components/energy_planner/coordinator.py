"""Coordinator for normalizing Energy Planner source data."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .battery_adapters import EnphaseBatteryAdapter
from .const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_RESERVE_PERCENT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_EXPORT_RATE,
    CONF_FIXED_MONTHLY_COST,
    CONF_FORECAST_SOLAR_ENTRY,
    CONF_PRICE_ENTITY,
    CONF_SUPPLIER_MARKUP,
    CONF_TARIFF_MODE,
    CONF_TOU_OFFPEAK_GRID_COST,
    CONF_TOU_PEAK_END_HOUR,
    CONF_TOU_PEAK_GRID_COST,
    CONF_TOU_PEAK_START_HOUR,
    CONF_VARIABLE_GRID_COST,
    DEFAULT_BATTERY_RESERVE_PERCENT,
    DEFAULT_EXPORT_RATE,
    DEFAULT_TARIFF_MODE,
    DEFAULT_TOU_OFFPEAK_GRID_COST,
    DEFAULT_TOU_PEAK_END_HOUR,
    DEFAULT_TOU_PEAK_GRID_COST,
    DEFAULT_TOU_PEAK_START_HOUR,
    DOMAIN,
    EXECUTION_AUTOMATIC,
    EXECUTION_NOTIFY_AT_START,
    MAX_PLAN_HISTORY,
    MODEL_STATUS_BATTERY_AWARE,
    MODEL_STATUS_COMPLETE,
    MODEL_STATUS_PRICE_ONLY,
    PLAN_STATUS_COMPLETED,
    PLAN_STATUS_MISSED,
    PLAN_STATUS_RUNNING,
    PLAN_STATUS_SCHEDULED,
)
from .cost_models import build_cost_model
from .price_adapters import DEFAULT_PRICE_ADAPTERS
from .pricing import PricePoint, PriceTimeline
from .profiles import ApplianceProfile, profile_map_from_storage
from .solar_adapters import ForecastSolarAdapter
from .storage import PlannerStorage

_LOGGER = logging.getLogger(__name__)


class EnergyPlannerCoordinator(DataUpdateCoordinator[PriceTimeline]):
    """Read and normalize the configured hourly electricity price sensor."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the price coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
            config_entry=entry,
        )
        self.config_entry = entry
        self.storage = PlannerStorage(hass, entry.entry_id)
        self.last_plan: dict[str, Any] | None = None
        self.plan_history: list[dict[str, Any]] = []
        self.profiles: dict[str, ApplianceProfile] = {}
        self.battery_snapshot: Any | None = None
        self.solar_forecast: Any | None = None
        self.model_status = MODEL_STATUS_PRICE_ONLY
        self.cost_model = None
        self._scheduled_unsubscribes: dict[str, list[Any]] = {}

    async def async_load_persisted_state(self) -> None:
        """Load plans and profiles before native entities are created."""
        try:
            stored = await self.storage.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Unable to load Energy Planner state: %s", err)
            return
        self.last_plan = stored["last_plan"]
        self.plan_history = stored["plan_history"][:MAX_PLAN_HISTORY]
        profiles = stored["profiles"]
        self.profiles = (
            profiles
            if isinstance(profiles, dict)
            else profile_map_from_storage(profiles)
        )

    async def async_save_persisted_state(self) -> None:
        """Persist plans and profiles using Home Assistant's versioned store."""
        await self.storage.async_save(
            last_plan=self.last_plan,
            plan_history=self.plan_history,
            profiles=self.profiles,
        )

    def set_last_plan(self, response: dict[str, Any]) -> dict[str, Any]:
        """Publish the latest plan response to native Home Assistant entities."""
        plan = dict(response)
        plan.setdefault("plan_id", uuid4().hex)
        plan.setdefault("created_at", datetime.now().astimezone().isoformat())
        self.last_plan = plan
        self.plan_history = [
            plan,
            *[
                previous
                for previous in self.plan_history
                if previous.get("plan_id") != plan["plan_id"]
            ],
        ][:MAX_PLAN_HISTORY]
        self.async_update_listeners()
        self.hass.async_create_task(
            self.async_save_persisted_state(),
            f"{DOMAIN}_save_{self.config_entry.entry_id}",
        )
        return dict(plan)

    def set_profile(self, profile: ApplianceProfile) -> None:
        """Create or replace a reusable appliance profile."""
        self.profiles[profile.profile_id] = profile
        self.async_update_listeners()
        self.hass.async_create_task(
            self.async_save_persisted_state(),
            f"{DOMAIN}_save_{self.config_entry.entry_id}",
        )

    def remove_profile(self, profile_id: str) -> bool:
        """Remove a profile and return whether it existed."""
        removed = self.profiles.pop(profile_id, None) is not None
        if removed:
            self.async_update_listeners()
            self.hass.async_create_task(
                self.async_save_persisted_state(),
                f"{DOMAIN}_save_{self.config_entry.entry_id}",
            )
        return removed

    async def async_set_plan_status(
        self, plan_id: str, status: str, **updates: Any
    ) -> dict[str, Any] | None:
        """Update one persisted plan while keeping the latest-plan entity current."""
        for plan in self.plan_history:
            if plan.get("plan_id") == plan_id:
                plan["status"] = status
                plan.update(updates)
                if self.last_plan and self.last_plan.get("plan_id") == plan_id:
                    self.last_plan = dict(plan)
                self.async_update_listeners()
                await self.async_save_persisted_state()
                return dict(plan)
        return None

    async def async_schedule_plan(
        self, plan: dict[str, Any], profile: ApplianceProfile
    ) -> dict[str, Any]:
        """Schedule a notification or strictly verified delayed-start action."""
        plan_id = str(plan.get("plan_id"))
        start = _parse_plan_datetime(plan.get("start_time"))
        end = _parse_plan_datetime(plan.get("end_time"))
        if not plan_id or start is None or end is None or start >= end:
            return plan
        if profile.execution_mode == EXECUTION_NOTIFY_AT_START:
            pass
        elif profile.execution_mode == EXECUTION_AUTOMATIC:
            reason = validate_automatic_profile(profile)
            if reason:
                return (
                    await self.async_set_plan_status(
                        plan_id, PLAN_STATUS_MISSED, reason=reason
                    )
                    or plan
                )
        else:
            return plan

        now = datetime.now().astimezone()
        if start <= now:
            return (
                await self.async_set_plan_status(
                    plan_id,
                    PLAN_STATUS_MISSED,
                    reason="The recommended start time has already passed",
                )
                or plan
            )
        if self._has_load_group_conflict(plan_id, start, end, profile):
            return (
                await self.async_set_plan_status(
                    plan_id,
                    PLAN_STATUS_MISSED,
                    reason="The plan conflicts with another scheduled load group",
                )
                or plan
            )

        scheduled = await self.async_set_plan_status(
            plan_id,
            PLAN_STATUS_SCHEDULED,
            scheduled_at=now.isoformat(),
            execution_mode=profile.execution_mode,
            profile_id=profile.profile_id,
        )
        self._scheduled_unsubscribes[plan_id] = [
            async_track_point_in_time(
                self.hass,
                lambda when: self._async_start_scheduled_plan(plan_id, profile, when),
                start,
            ),
            async_track_point_in_time(
                self.hass,
                lambda when: self._async_finish_scheduled_plan(plan_id, when),
                end,
            ),
        ]
        return scheduled or plan

    def _has_load_group_conflict(
        self,
        plan_id: str,
        start: datetime,
        end: datetime,
        profile: ApplianceProfile,
    ) -> bool:
        """Return whether another scheduled plan occupies the same load group."""
        if not profile.load_group:
            return False
        active_statuses = {"recommended", PLAN_STATUS_SCHEDULED, PLAN_STATUS_RUNNING}
        for other in self.plan_history:
            if (
                other.get("plan_id") == plan_id
                or other.get("status") not in active_statuses
            ):
                continue
            other_profile = self.profiles.get(other.get("profile_id"))
            if other_profile is None or other_profile.load_group != profile.load_group:
                continue
            other_start = _parse_plan_datetime(other.get("start_time"))
            other_end = _parse_plan_datetime(other.get("end_time"))
            if other_start and other_end and other_start < end and start < other_end:
                return True
        return False

    async def async_restore_scheduled_plans(self) -> None:
        """Re-arm future notifications after a Home Assistant restart."""
        for plan in list(self.plan_history):
            if plan.get("status") != PLAN_STATUS_SCHEDULED:
                continue
            profile_id = plan.get("profile_id")
            profile = self.profiles.get(profile_id)
            if profile is None:
                await self.async_set_plan_status(
                    str(plan.get("plan_id")),
                    PLAN_STATUS_MISSED,
                    reason="The saved appliance profile no longer exists",
                )
                continue
            await self.async_schedule_plan(plan, profile)

    async def _async_start_scheduled_plan(
        self, plan_id: str, profile: ApplianceProfile, when: datetime
    ) -> None:
        """Deliver the scheduled notification or perform the guarded action."""
        del when
        plan = next(
            (item for item in self.plan_history if item.get("plan_id") == plan_id),
            None,
        )
        if plan is None:
            return
        deadline = _parse_plan_datetime(plan.get("deadline"))
        now = datetime.now().astimezone()
        if deadline is None or now > deadline:
            await self.async_set_plan_status(
                plan_id, PLAN_STATUS_MISSED, reason="The plan deadline has passed"
            )
            return

        if profile.execution_mode == EXECUTION_NOTIFY_AT_START:
            persistent_notification.async_create(
                self.hass,
                _notification_message(plan, profile),
                title="Energy Planner recommendation",
                notification_id=f"energy_planner_{plan_id}",
            )
            await self.async_set_plan_status(plan_id, PLAN_STATUS_RUNNING)
            return

        reason = validate_automatic_profile(profile)
        if reason:
            await self.async_set_plan_status(plan_id, PLAN_STATUS_MISSED, reason=reason)
            return
        if (
            not self.last_update_success
            or self.data is None
            or self.data.current is None
        ):
            await self.async_set_plan_status(
                plan_id,
                PLAN_STATUS_MISSED,
                reason=(
                    "Current price data is unavailable or stale; automatic start "
                    "was blocked"
                ),
            )
            return
        power_state = self.hass.states.get(profile.power_entity)
        power = _parse_power_watts(power_state)
        if power is None:
            await self.async_set_plan_status(
                plan_id,
                PLAN_STATUS_MISSED,
                reason="Power monitoring is unavailable; automatic start was blocked",
            )
            return
        if power > profile.power_threshold_w:
            await self.async_set_plan_status(
                plan_id,
                PLAN_STATUS_MISSED,
                reason="Power monitoring shows the load is already active",
            )
            return

        domain, service = profile.start_service.split(".", 1)
        service_data = {**profile.service_data, "entity_id": profile.start_entity}
        await self.hass.services.async_call(
            domain, service, service_data, blocking=True
        )
        await self.async_set_plan_status(
            plan_id, PLAN_STATUS_RUNNING, started_at=now.isoformat()
        )

    async def _async_finish_scheduled_plan(self, plan_id: str, when: datetime) -> None:
        """Mark a successfully reached plan window complete."""
        del when
        plan = next(
            (item for item in self.plan_history if item.get("plan_id") == plan_id),
            None,
        )
        if plan and plan.get("status") == PLAN_STATUS_RUNNING:
            await self.async_set_plan_status(
                plan_id,
                PLAN_STATUS_COMPLETED,
                completed_at=datetime.now().astimezone().isoformat(),
            )

    async def async_shutdown(self) -> None:
        """Cancel timers owned by this config entry."""
        for callbacks in self._scheduled_unsubscribes.values():
            for unsubscribe in callbacks:
                unsubscribe()
        self._scheduled_unsubscribes.clear()

    async def _async_update_data(self) -> PriceTimeline:
        """Return a normalized adjusted price timeline from the source sensor."""
        source_entity = self.config_entry.options.get(
            CONF_PRICE_ENTITY, self.config_entry.data[CONF_PRICE_ENTITY]
        )
        state = self.hass.states.get(source_entity)
        if state is None:
            raise UpdateFailed(f"Price source {source_entity} is unavailable")

        try:
            spot_timeline = DEFAULT_PRICE_ADAPTERS.select(state.attributes).normalize(
                state.attributes
            )
            settings = self._settings()
            cost_model = build_cost_model(
                {
                    "tariff": settings[CONF_TARIFF_MODE],
                    "supplier_markup": settings[CONF_SUPPLIER_MARKUP],
                    "variable_grid_cost": settings[CONF_VARIABLE_GRID_COST],
                    "monthly_fixed_cost": settings[CONF_FIXED_MONTHLY_COST],
                    "peak_markup": settings[CONF_SUPPLIER_MARKUP]
                    + settings[CONF_VARIABLE_GRID_COST]
                    + settings[CONF_TOU_PEAK_GRID_COST],
                    "off_peak_markup": settings[CONF_SUPPLIER_MARKUP]
                    + settings[CONF_VARIABLE_GRID_COST]
                    + settings[CONF_TOU_OFFPEAK_GRID_COST],
                    "peak_start": f"{settings[CONF_TOU_PEAK_START_HOUR]:02d}:00",
                    "peak_end": f"{settings[CONF_TOU_PEAK_END_HOUR]:02d}:00",
                    "export_compensation": settings[CONF_EXPORT_RATE],
                }
            )
            self.cost_model = cost_model
            await self._async_refresh_optional_sources(settings)
            self.model_status = (
                MODEL_STATUS_COMPLETE
                if self.battery_snapshot is not None and self.solar_forecast is not None
                else MODEL_STATUS_BATTERY_AWARE
                if self.battery_snapshot is not None
                else MODEL_STATUS_PRICE_ONLY
            )
            return PriceTimeline(
                points=tuple(
                    PricePoint(
                        start_time=point.start_time,
                        end_time=point.end_time,
                        spot_price_per_kwh=point.spot_price_per_kwh,
                        price_per_kwh=cost_model.import_price(
                            point.spot_price_per_kwh, point.start_time
                        ),
                    )
                    for point in spot_timeline.points
                ),
                source_format=spot_timeline.source_format,
            )
        except ValueError as err:
            raise UpdateFailed(str(err)) from err

    def _settings(self) -> dict[str, Any]:
        """Return current options with safe defaults for older entries."""
        values = {**self.config_entry.data, **self.config_entry.options}
        return {
            CONF_SUPPLIER_MARKUP: float(values.get(CONF_SUPPLIER_MARKUP, 0.0)),
            CONF_VARIABLE_GRID_COST: float(values.get(CONF_VARIABLE_GRID_COST, 0.0)),
            CONF_FIXED_MONTHLY_COST: float(values.get(CONF_FIXED_MONTHLY_COST, 0.0)),
            CONF_TARIFF_MODE: values.get(CONF_TARIFF_MODE, DEFAULT_TARIFF_MODE),
            CONF_TOU_PEAK_GRID_COST: float(
                values.get(CONF_TOU_PEAK_GRID_COST, DEFAULT_TOU_PEAK_GRID_COST)
            ),
            CONF_TOU_OFFPEAK_GRID_COST: float(
                values.get(CONF_TOU_OFFPEAK_GRID_COST, DEFAULT_TOU_OFFPEAK_GRID_COST)
            ),
            CONF_TOU_PEAK_START_HOUR: int(
                values.get(CONF_TOU_PEAK_START_HOUR, DEFAULT_TOU_PEAK_START_HOUR)
            ),
            CONF_TOU_PEAK_END_HOUR: int(
                values.get(CONF_TOU_PEAK_END_HOUR, DEFAULT_TOU_PEAK_END_HOUR)
            ),
            CONF_EXPORT_RATE: float(values.get(CONF_EXPORT_RATE, DEFAULT_EXPORT_RATE)),
            CONF_BATTERY_SOC_ENTITY: values.get(CONF_BATTERY_SOC_ENTITY),
            CONF_BATTERY_CAPACITY_ENTITY: values.get(CONF_BATTERY_CAPACITY_ENTITY),
            CONF_BATTERY_CHARGE_POWER_ENTITY: values.get(
                CONF_BATTERY_CHARGE_POWER_ENTITY
            ),
            CONF_BATTERY_DISCHARGE_POWER_ENTITY: values.get(
                CONF_BATTERY_DISCHARGE_POWER_ENTITY
            ),
            CONF_BATTERY_RESERVE_PERCENT: float(
                values.get(
                    CONF_BATTERY_RESERVE_PERCENT, DEFAULT_BATTERY_RESERVE_PERCENT
                )
            ),
            CONF_FORECAST_SOLAR_ENTRY: values.get(CONF_FORECAST_SOLAR_ENTRY),
        }

    async def _async_refresh_optional_sources(self, settings: dict[str, Any]) -> None:
        """Refresh optional battery and solar inputs without breaking prices."""
        self.battery_snapshot = None
        self.solar_forecast = None
        soc_entity = settings.get(CONF_BATTERY_SOC_ENTITY)
        capacity_entity = settings.get(CONF_BATTERY_CAPACITY_ENTITY)
        if soc_entity and capacity_entity:
            try:
                self.battery_snapshot = await EnphaseBatteryAdapter(
                    self.hass,
                    soc_entity,
                    capacity_entity,
                    settings.get(CONF_BATTERY_CHARGE_POWER_ENTITY),
                    reserve_percent=settings[CONF_BATTERY_RESERVE_PERCENT],
                    discharge_power_entity=settings.get(
                        CONF_BATTERY_DISCHARGE_POWER_ENTITY
                    ),
                ).async_snapshot()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Battery adapter unavailable: %s", err)

        forecast_entry = settings.get(CONF_FORECAST_SOLAR_ENTRY)
        if forecast_entry:
            try:
                self.solar_forecast = await ForecastSolarAdapter(
                    self.hass, forecast_entry
                ).async_forecast()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Forecast.Solar adapter unavailable: %s", err)


def _parse_plan_datetime(value: Any) -> datetime | None:
    """Parse a timezone-aware plan timestamp."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _parse_power_watts(state: Any) -> float | None:
    """Parse a power-monitor state into watts."""
    if state is None:
        return None
    try:
        value = float(state.state)
    except (AttributeError, TypeError, ValueError):
        return None
    unit = str(getattr(state, "attributes", {}).get("unit_of_measurement", "W")).lower()
    if unit in {"kw", "kilowatt", "kilowatts"}:
        value *= 1000
    return value if value >= 0 else None


def validate_automatic_profile(profile: ApplianceProfile) -> str | None:
    """Return a fail-closed reason when an automatic profile is unsafe."""
    if not profile.enabled:
        return "The appliance profile is disabled"
    if not profile.verified_delayed_start:
        return "Automatic mode requires verified delayed-start capability"
    if not profile.start_entity or not profile.start_service:
        return "Automatic mode requires a target entity and delayed-start service"
    if not profile.power_entity:
        return "Automatic mode requires a power-monitoring entity"
    if "." not in profile.start_service:
        return "The delayed-start service must use domain.service format"
    domain, service = profile.start_service.split(".", 1)
    if not domain or not service:
        return "The delayed-start service must use domain.service format"
    if domain in {
        "switch",
        "light",
        "fan",
        "cover",
        "lock",
        "scene",
        "script",
        "automation",
        "input_boolean",
        "homeassistant",
    }:
        return "Generic immediate-control services are not allowed in automatic mode"
    if profile.power_threshold_w <= 0:
        return "Automatic mode requires a positive power threshold"
    return None


def _notification_message(plan: dict[str, Any], profile: ApplianceProfile) -> str:
    """Format the start notification without exposing device-control details."""
    return (
        f"{profile.name} is planned for {plan.get('duration_minutes')} minutes "
        f"from {plan.get('start_time')} to {plan.get('end_time')}. "
        "Energy Planner has not started the appliance."
    )
