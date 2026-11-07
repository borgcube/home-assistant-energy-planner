"""Planning, profile, and guarded execution services for Energy Planner."""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_PRICE_ENTITY,
    DOMAIN,
    EXECUTION_AUTOMATIC,
    EXECUTION_NOTIFY_AT_START,
    EXECUTION_PLAN_ONLY,
    MODEL_STATUS_PRICE_ONLY,
    MODEL_STATUS_UNAVAILABLE,
    SERVICE_APPLIANCE_ID,
    SERVICE_AVERAGE_POWER_KW,
    SERVICE_CHARGE_POWER_KW,
    SERVICE_DEADLINE,
    SERVICE_DURATION_MINUTES,
    SERVICE_EARLIEST_START,
    SERVICE_ENABLED,
    SERVICE_ENERGY_ENTITY,
    SERVICE_ENTRY_ID,
    SERVICE_EXECUTION_MODE,
    SERVICE_LOAD_GROUP,
    SERVICE_POWER_ENTITY,
    SERVICE_POWER_THRESHOLD_W,
    SERVICE_PROFILE_ID,
    SERVICE_PROFILE_NAME,
    SERVICE_SERVICE_DATA,
    SERVICE_START_ENTITY,
    SERVICE_START_SERVICE,
    SERVICE_VERIFIED_DELAYED_START,
)
from .energy_usage import async_estimate_appliance_usage
from .planning import AppliancePlanRequest, ScheduledWindow, find_lowest_cost_window
from .pricing import PriceTimeline
from .profiles import ApplianceProfile


def _quarter_hour_duration(value: int) -> int:
    """Require durations to use the planner's 15-minute precision."""
    if value % 15:
        raise vol.Invalid("duration_minutes must use 15-minute increments")
    return value


def _ensure_timezone(value: datetime, local_timezone: tzinfo) -> datetime:
    """Interpret Home Assistant's naive picker values in local time."""
    return value if value.tzinfo is not None else value.replace(tzinfo=local_timezone)


PLAN_APPLIANCE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_APPLIANCE_ID): vol.All(
            cv.string, vol.Length(min=1, max=64)
        ),
        vol.Required(SERVICE_DURATION_MINUTES): vol.All(
            vol.Coerce(int),
            vol.Range(min=15, max=24 * 60),
            _quarter_hour_duration,
        ),
        vol.Required(SERVICE_DEADLINE): cv.datetime,
        vol.Optional(SERVICE_EARLIEST_START): cv.datetime,
        vol.Optional(SERVICE_AVERAGE_POWER_KW): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=100)
        ),
        vol.Optional(SERVICE_ENERGY_ENTITY): cv.entity_id,
        vol.Optional(SERVICE_ENTRY_ID): cv.string,
    }
)

PLAN_BATTERY_CHARGE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_DURATION_MINUTES): vol.All(
            vol.Coerce(int),
            vol.Range(min=15, max=24 * 60),
            _quarter_hour_duration,
        ),
        vol.Required(SERVICE_DEADLINE): cv.datetime,
        vol.Optional(SERVICE_EARLIEST_START): cv.datetime,
        vol.Required(SERVICE_CHARGE_POWER_KW): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=100)
        ),
        vol.Optional(SERVICE_ENTRY_ID): cv.string,
    }
)

SAVE_APPLIANCE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_PROFILE_ID): vol.All(cv.string, vol.Length(min=1, max=64)),
        vol.Required(SERVICE_PROFILE_NAME): vol.All(
            cv.string, vol.Length(min=1, max=100)
        ),
        vol.Required(SERVICE_DURATION_MINUTES): vol.All(
            vol.Coerce(int), vol.Range(min=15, max=24 * 60), _quarter_hour_duration
        ),
        vol.Optional(SERVICE_AVERAGE_POWER_KW): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=100)
        ),
        vol.Optional(SERVICE_ENERGY_ENTITY): cv.entity_id,
        vol.Optional(SERVICE_EXECUTION_MODE, default=EXECUTION_PLAN_ONLY): vol.In(
            (EXECUTION_PLAN_ONLY, EXECUTION_NOTIFY_AT_START, EXECUTION_AUTOMATIC)
        ),
        vol.Optional(SERVICE_START_ENTITY): cv.string,
        vol.Optional(SERVICE_START_SERVICE): cv.string,
        vol.Optional(SERVICE_SERVICE_DATA, default={}): dict,
        vol.Optional(SERVICE_VERIFIED_DELAYED_START, default=False): cv.boolean,
        vol.Optional(SERVICE_ENABLED, default=True): cv.boolean,
        vol.Optional(SERVICE_POWER_ENTITY): cv.string,
        vol.Optional(SERVICE_POWER_THRESHOLD_W, default=50.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=100000)
        ),
        vol.Optional(SERVICE_LOAD_GROUP): cv.string,
        vol.Optional(SERVICE_ENTRY_ID): cv.string,
    }
)

REMOVE_APPLIANCE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_PROFILE_ID): vol.All(cv.string, vol.Length(min=1, max=64)),
        vol.Optional(SERVICE_ENTRY_ID): cv.string,
    }
)

PLAN_APPLIANCE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_PROFILE_ID): vol.All(cv.string, vol.Length(min=1, max=64)),
        vol.Required(SERVICE_DEADLINE): cv.datetime,
        vol.Optional(SERVICE_EARLIEST_START): cv.datetime,
        vol.Optional(SERVICE_ENTRY_ID): cv.string,
    }
)


def build_plan_response(
    timeline: PriceTimeline,
    request: AppliancePlanRequest,
    window: ScheduledWindow | None,
    *,
    source_entity: str,
    plan_type: str | None = None,
    target_energy_kwh: float | None = None,
    execution_mode: str = EXECUTION_PLAN_ONLY,
    model_status: str | None = None,
    profile_id: str | None = None,
    usage_summary: dict[str, Any] | None = None,
) -> ServiceResponse:
    """Build a JSON-safe, plan-only response for a service caller."""
    response: dict[str, Any] = {
        SERVICE_APPLIANCE_ID: request.appliance_id,
        "status": "recommended" if window else "unavailable",
        "execution_mode": execution_mode,
        "model_status": model_status
        or (MODEL_STATUS_PRICE_ONLY if window else MODEL_STATUS_UNAVAILABLE),
        SERVICE_DURATION_MINUTES: int(request.duration.total_seconds() / 60),
        SERVICE_AVERAGE_POWER_KW: request.average_power_kw,
        SERVICE_EARLIEST_START: request.earliest_start.isoformat()
        if request.earliest_start
        else None,
        SERVICE_DEADLINE: request.deadline.isoformat(),
        "source_entity": source_entity,
        "source_format": timeline.source_format,
        "resolution_minutes": timeline.resolution_minutes,
    }
    if plan_type is not None:
        response["plan_type"] = plan_type
    if target_energy_kwh is not None:
        response["target_energy_kwh"] = target_energy_kwh
    if profile_id is not None:
        response[SERVICE_PROFILE_ID] = profile_id
    if usage_summary:
        response.update(usage_summary)
    if window is None:
        response["reason"] = "No contiguous price window meets the request"
        return response

    energy_kwh = request.average_power_kw * request.duration.total_seconds() / 3600
    current = timeline.current
    reference_cost = current.price_per_kwh * energy_kwh if current else None
    response.update(
        {
            "start_time": window.start_time.isoformat(),
            "end_time": window.end_time.isoformat(),
            "estimated_cost": window.estimated_cost,
            "average_price_per_kwh": window.average_price_per_kwh,
            "estimated_saving_vs_current": (
                reference_cost - window.estimated_cost
                if reference_cost is not None
                else None
            ),
        }
    )
    return response


async def _resolve_average_power_kw(
    hass: HomeAssistant,
    *,
    energy_entity: str | None,
    fallback_power_kw: float | None,
) -> tuple[float, dict[str, Any] | None]:
    """Resolve manual or history-derived appliance power for a plan."""
    if energy_entity:
        try:
            usage_summary = await async_estimate_appliance_usage(hass, energy_entity)
        except HomeAssistantError:
            if fallback_power_kw is None:
                raise
        else:
            return float(usage_summary["historical_average_power_kw"]), usage_summary
    if fallback_power_kw is None:
        raise HomeAssistantError(
            "Provide average_power_kw or select an energy_entity with usable history"
        )
    return float(fallback_power_kw), None


def _select_coordinator(
    hass: HomeAssistant, requested_entry_id: str | None
) -> tuple[Any, str]:
    """Select the loaded planner entry for a service request."""
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if (
            entry.state is ConfigEntryState.LOADED
            and getattr(entry, "runtime_data", None)
        )
    ]
    if requested_entry_id:
        for entry in entries:
            if entry.entry_id == requested_entry_id:
                return entry.runtime_data, entry.entry_id
        raise HomeAssistantError(
            f"Energy Planner entry {requested_entry_id} is not loaded"
        )
    if len(entries) != 1:
        raise HomeAssistantError(
            "Specify entry_id when zero or multiple Energy Planner entries are loaded"
        )
    entry = entries[0]
    return entry.runtime_data, entry.entry_id


async def async_plan_appliance(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return a cheapest appliance plan without controlling a device."""
    average_power_kw, usage_summary = await _resolve_average_power_kw(
        hass,
        energy_entity=call.data.get(SERVICE_ENERGY_ENTITY),
        fallback_power_kw=call.data.get(SERVICE_AVERAGE_POWER_KW),
    )
    return await _async_plan(
        hass,
        call,
        appliance_id=call.data[SERVICE_APPLIANCE_ID],
        average_power_kw=average_power_kw,
        usage_summary=usage_summary,
    )


async def async_plan_battery_charge(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Return a price-only battery charge plan without controlling a battery."""
    duration_hours = call.data[SERVICE_DURATION_MINUTES] / 60
    charge_power_kw = call.data[SERVICE_CHARGE_POWER_KW]
    return await _async_plan(
        hass,
        call,
        appliance_id="battery_grid_charge",
        average_power_kw=charge_power_kw,
        plan_type="battery_charge",
        target_energy_kwh=charge_power_kw * duration_hours,
    )


async def async_save_appliance_profile(hass: HomeAssistant, call: ServiceCall) -> None:
    """Save a reusable appliance profile without executing anything."""
    coordinator, _entry_id = _select_coordinator(hass, call.data.get(SERVICE_ENTRY_ID))
    energy_entity = call.data.get(SERVICE_ENERGY_ENTITY)
    average_power_kw, _usage_summary = await _resolve_average_power_kw(
        hass,
        energy_entity=energy_entity,
        fallback_power_kw=call.data.get(SERVICE_AVERAGE_POWER_KW),
    )
    coordinator.set_profile(
        ApplianceProfile(
            profile_id=call.data[SERVICE_PROFILE_ID],
            name=call.data[SERVICE_PROFILE_NAME],
            duration_minutes=call.data[SERVICE_DURATION_MINUTES],
            average_power_kw=average_power_kw,
            energy_entity=energy_entity,
            execution_mode=call.data[SERVICE_EXECUTION_MODE],
            start_entity=call.data.get(SERVICE_START_ENTITY),
            start_service=call.data.get(SERVICE_START_SERVICE),
            service_data=dict(call.data.get(SERVICE_SERVICE_DATA) or {}),
            verified_delayed_start=call.data[SERVICE_VERIFIED_DELAYED_START],
            enabled=call.data[SERVICE_ENABLED],
            power_entity=call.data.get(SERVICE_POWER_ENTITY),
            power_threshold_w=call.data[SERVICE_POWER_THRESHOLD_W],
            load_group=call.data.get(SERVICE_LOAD_GROUP),
        )
    )


async def async_remove_appliance_profile(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Remove a stored appliance profile."""
    coordinator, _entry_id = _select_coordinator(hass, call.data.get(SERVICE_ENTRY_ID))
    if not coordinator.remove_profile(call.data[SERVICE_PROFILE_ID]):
        raise HomeAssistantError(
            f"Appliance profile {call.data[SERVICE_PROFILE_ID]} does not exist"
        )


async def async_plan_appliance_profile(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Plan a saved profile and optionally schedule its safe execution mode."""
    coordinator, _entry_id = _select_coordinator(hass, call.data.get(SERVICE_ENTRY_ID))
    profile = coordinator.profiles.get(call.data[SERVICE_PROFILE_ID])
    if profile is None:
        raise HomeAssistantError(
            f"Appliance profile {call.data[SERVICE_PROFILE_ID]} does not exist"
        )
    if not profile.enabled:
        raise HomeAssistantError(f"Appliance profile {profile.profile_id} is disabled")
    average_power_kw, usage_summary = await _resolve_average_power_kw(
        hass,
        energy_entity=profile.energy_entity,
        fallback_power_kw=profile.average_power_kw,
    )
    response = await _async_plan(
        hass,
        call,
        appliance_id=profile.profile_id,
        average_power_kw=average_power_kw,
        usage_summary=usage_summary,
        execution_mode=profile.execution_mode,
        profile_id=profile.profile_id,
        duration_minutes=profile.duration_minutes,
    )
    if response.get("status") == "recommended":
        response = await coordinator.async_schedule_plan(response, profile)
    return response


async def _async_plan(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    appliance_id: str,
    average_power_kw: float,
    plan_type: str | None = None,
    target_energy_kwh: float | None = None,
    execution_mode: str = EXECUTION_PLAN_ONLY,
    profile_id: str | None = None,
    duration_minutes: int | None = None,
    usage_summary: dict[str, Any] | None = None,
) -> ServiceResponse:
    """Build a plan response from the shared, read-only planning path."""
    coordinator, entry_id = _select_coordinator(hass, call.data.get(SERVICE_ENTRY_ID))
    timeline = coordinator.data
    if timeline is None:
        raise HomeAssistantError("Energy Planner has no current price timeline")

    now = datetime.now().astimezone()
    deadline = _ensure_timezone(call.data[SERVICE_DEADLINE], now.tzinfo)
    earliest_start = _ensure_timezone(
        call.data.get(SERVICE_EARLIEST_START, now), now.tzinfo
    )
    requested_duration_minutes = duration_minutes or call.data[SERVICE_DURATION_MINUTES]
    requested_energy_kwh = average_power_kw * requested_duration_minutes / 60
    battery_headroom: float | None = None
    effective_duration_minutes = requested_duration_minutes
    snapshot = coordinator.battery_snapshot if plan_type == "battery_charge" else None
    if snapshot is not None:
        battery_headroom = max(
            0.0,
            snapshot.usable_capacity_kwh * (1 - snapshot.reserve_percent / 100)
            - snapshot.usable_capacity_kwh * snapshot.state_of_charge,
        )
        effective_duration_minutes = min(
            requested_duration_minutes,
            int((battery_headroom / average_power_kw) * 60 // 15 * 15),
        )
    request = AppliancePlanRequest(
        appliance_id=appliance_id,
        duration=timedelta(minutes=effective_duration_minutes),
        deadline=deadline,
        average_power_kw=average_power_kw,
        earliest_start=earliest_start,
    )
    window = (
        find_lowest_cost_window(timeline, request)
        if effective_duration_minutes >= 15
        else None
    )
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"Energy Planner entry {entry_id} was removed")
    source_entity = entry.options.get(CONF_PRICE_ENTITY, entry.data[CONF_PRICE_ENTITY])
    response = build_plan_response(
        timeline,
        request,
        window,
        source_entity=source_entity,
        plan_type=plan_type,
        target_energy_kwh=target_energy_kwh,
        execution_mode=execution_mode,
        model_status=coordinator.model_status if window else None,
        profile_id=profile_id,
        usage_summary=usage_summary,
    )
    if plan_type == "battery_charge" and coordinator.battery_snapshot is not None:
        response["battery_state_of_charge"] = snapshot.state_of_charge
        response["battery_headroom_kwh"] = battery_headroom
        response["requested_energy_kwh"] = requested_energy_kwh
        response["target_energy_kwh"] = min(
            target_energy_kwh
            if target_energy_kwh is not None
            else requested_energy_kwh,
            battery_headroom or 0.0,
        )
        response["battery_limited"] = (battery_headroom or 0.0) < requested_energy_kwh
        if effective_duration_minutes != requested_duration_minutes:
            response["requested_duration_minutes"] = requested_duration_minutes
    if plan_type == "battery_charge" and coordinator.solar_forecast is not None:
        response["solar_forecast_kwh"] = sum(
            point.energy_kwh
            for point in coordinator.solar_forecast.points
            if point.end_time > earliest_start and point.start_time < deadline
        )
    response = coordinator.set_last_plan(response)
    return response
