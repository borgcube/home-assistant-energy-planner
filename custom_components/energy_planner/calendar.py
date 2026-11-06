"""Calendar entity for the latest Energy Planner recommendation."""

from __future__ import annotations

import datetime as dt
from typing import Any, override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import EnergyPlannerConfigEntry
from .const import DOMAIN, PLANNER_NAME
from .coordinator import EnergyPlannerCoordinator


def _parse_plan_datetime(value: Any) -> dt.datetime | None:
    """Parse an ISO timestamp from a plan response."""
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        return None
    return dt_util.as_local(parsed)


def _plan_label(plan: dict[str, Any]) -> str:
    """Return a human-readable event title for a plan response."""
    if plan.get("plan_type") == "battery_charge":
        return "Battery charge plan"
    appliance_id = str(plan.get("appliance_id") or "appliance").replace("_", " ")
    return f"Appliance plan: {appliance_id}"


def _format_euro(value: Any) -> str | None:
    """Format a numeric plan value as a compact euro amount."""
    if not isinstance(value, (int, float)):
        return None
    return f"€{value:.2f}"


def _plan_description(plan: dict[str, Any]) -> str:
    """Return useful context for the native calendar event."""
    lines = [
        "Price-only recommendation; no device control is performed.",
        f"Model: {plan.get('model_status', 'unknown')}",
        f"Execution: {plan.get('execution_mode', 'plan_only')}",
    ]

    if plan.get("target_energy_kwh") is not None:
        lines.append(f"Target energy: {plan['target_energy_kwh']} kWh")
    if plan.get("duration_minutes") is not None:
        lines.append(f"Duration: {plan['duration_minutes']} minutes")
    if plan.get("average_power_kw") is not None:
        lines.append(f"Average power: {plan['average_power_kw']} kW")
    if plan.get("estimated_cost") is not None:
        cost = _format_euro(plan["estimated_cost"])
        lines.append(f"Estimated cost: {cost or plan['estimated_cost']}")
    if plan.get("estimated_saving_vs_current") is not None:
        saving = _format_euro(plan["estimated_saving_vs_current"])
        lines.append(
            f"Estimated saving: {saving or plan['estimated_saving_vs_current']}"
        )
    if plan.get("source_entity"):
        lines.append(f"Price source: {plan['source_entity']}")
    if plan.get("resolution_minutes") is not None:
        lines.append(f"Price resolution: {plan['resolution_minutes']} minutes")

    return "\n".join(lines)


def plan_to_calendar_event(
    plan: dict[str, Any] | None, entry_id: str
) -> CalendarEvent | None:
    """Convert a recommended plan response into a native calendar event."""
    if not plan or plan.get("status") != "recommended":
        return None

    start = _parse_plan_datetime(plan.get("start_time"))
    end = _parse_plan_datetime(plan.get("end_time"))
    if start is None or end is None or start >= end:
        return None

    return CalendarEvent(
        start=start,
        end=end,
        summary=_plan_label(plan),
        description=_plan_description(plan),
        uid=f"{entry_id}-last-plan",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergyPlannerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the latest-plan calendar for a config entry."""
    del hass
    async_add_entities([EnergyPlannerCalendar(entry.runtime_data, entry)])


class EnergyPlannerCalendar(
    CoordinatorEntity[EnergyPlannerCoordinator], CalendarEntity
):
    """Expose the latest plan as a read-only native calendar event."""

    _attr_has_entity_name = True
    _attr_name = "Plan schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self, coordinator: EnergyPlannerCoordinator, entry: EnergyPlannerConfigEntry
    ) -> None:
        """Initialize the plan calendar."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_plan_schedule"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=PLANNER_NAME,
            manufacturer="Energy Planner",
            model="Hourly price planner",
        )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the latest recommended plan event."""
        return plan_to_calendar_event(
            self.coordinator.last_plan, self._entry.entry_id
        )

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return the latest plan when it overlaps the requested range."""
        del hass
        event = self.event
        if event is None:
            return []
        if (
            event.start_datetime_local >= end_date
            or event.end_datetime_local <= start_date
        ):
            return []
        return [event]
