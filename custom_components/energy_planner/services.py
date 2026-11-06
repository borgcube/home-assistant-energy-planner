"""Read-only Home Assistant services for Energy Planner."""

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
    MODEL_STATUS_PRICE_ONLY,
    MODEL_STATUS_UNAVAILABLE,
    SERVICE_APPLIANCE_ID,
    SERVICE_AVERAGE_POWER_KW,
    SERVICE_CHARGE_POWER_KW,
    SERVICE_DEADLINE,
    SERVICE_DURATION_MINUTES,
    SERVICE_EARLIEST_START,
    SERVICE_ENTRY_ID,
)
from .planning import AppliancePlanRequest, ScheduledWindow, find_lowest_cost_window
from .pricing import PriceTimeline


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
        vol.Required(SERVICE_AVERAGE_POWER_KW): vol.All(
            vol.Coerce(float), vol.Range(min=0.001, max=100)
        ),
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


def build_plan_response(
    timeline: PriceTimeline,
    request: AppliancePlanRequest,
    window: ScheduledWindow | None,
    *,
    source_entity: str,
    plan_type: str | None = None,
    target_energy_kwh: float | None = None,
) -> ServiceResponse:
    """Build a JSON-safe, plan-only response for a service caller."""
    response: dict[str, Any] = {
        SERVICE_APPLIANCE_ID: request.appliance_id,
        "status": "recommended" if window else "unavailable",
        "execution_mode": "plan_only",
        "model_status": MODEL_STATUS_PRICE_ONLY if window else MODEL_STATUS_UNAVAILABLE,
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
    return await _async_plan(
        hass,
        call,
        appliance_id=call.data[SERVICE_APPLIANCE_ID],
        average_power_kw=call.data[SERVICE_AVERAGE_POWER_KW],
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


async def _async_plan(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    appliance_id: str,
    average_power_kw: float,
    plan_type: str | None = None,
    target_energy_kwh: float | None = None,
) -> ServiceResponse:
    """Build a plan response from the shared, read-only planning path."""
    coordinator, entry_id = _select_coordinator(
        hass, call.data.get(SERVICE_ENTRY_ID)
    )
    timeline = coordinator.data
    if timeline is None:
        raise HomeAssistantError("Energy Planner has no current price timeline")

    now = datetime.now().astimezone()
    deadline = _ensure_timezone(call.data[SERVICE_DEADLINE], now.tzinfo)
    earliest_start = _ensure_timezone(
        call.data.get(SERVICE_EARLIEST_START, now), now.tzinfo
    )
    request = AppliancePlanRequest(
        appliance_id=appliance_id,
        duration=timedelta(minutes=call.data[SERVICE_DURATION_MINUTES]),
        deadline=deadline,
        average_power_kw=average_power_kw,
        earliest_start=earliest_start,
    )
    window = find_lowest_cost_window(timeline, request)
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        raise HomeAssistantError(f"Energy Planner entry {entry_id} was removed")
    source_entity = entry.options.get(
        CONF_PRICE_ENTITY, entry.data[CONF_PRICE_ENTITY]
    )
    return build_plan_response(
        timeline,
        request,
        window,
        source_entity=source_entity,
        plan_type=plan_type,
        target_energy_kwh=target_energy_kwh,
    )
