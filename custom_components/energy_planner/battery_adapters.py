"""Battery provider adapters for Home Assistant entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from .contracts import BatterySnapshot


@dataclass(frozen=True, slots=True)
class EnphaseBatteryAdapter:
    """Adapt the aggregated Enphase battery entities exposed by Home Assistant."""

    hass: Any
    state_of_charge_entity: str
    capacity_entity: str
    charge_power_entity: str | None = None
    reserve_entity: str | None = None
    discharge_power_entity: str | None = None
    reserve_percent: float = 0.0
    key: str = "enphase_battery"

    async def async_snapshot(self) -> BatterySnapshot | None:
        """Return a normalized snapshot, or ``None`` for incomplete state."""
        soc_state = self._state(self.state_of_charge_entity)
        capacity_state = self._state(self.capacity_entity)
        if soc_state is None or capacity_state is None:
            return None

        state_of_charge = _parse_soc(soc_state)
        capacity_kwh = _parse_energy_kwh(capacity_state)
        if state_of_charge is None or capacity_kwh is None or capacity_kwh <= 0:
            return None

        reserve = self.reserve_percent
        if self.reserve_entity is not None:
            reserve_state = self._state(self.reserve_entity)
            parsed_reserve = _parse_percent(reserve_state)
            if parsed_reserve is None:
                return None
            reserve = parsed_reserve
        if not 0 <= reserve <= 100:
            return None

        charge_kw = _optional_power_kw(self._state(self.charge_power_entity))
        discharge_kw = _optional_power_kw(
            self._state(self.discharge_power_entity)
        )
        captured_at = _captured_at(soc_state, capacity_state)
        return BatterySnapshot(
            captured_at=captured_at,
            state_of_charge=state_of_charge,
            usable_capacity_kwh=capacity_kwh,
            reserve_percent=reserve,
            charging_power_kw=charge_kw,
            discharging_power_kw=discharge_kw,
        )

    def _state(self, entity_id: str | None) -> Any | None:
        if entity_id is None:
            return None
        return self.hass.states.get(entity_id)


def _captured_at(*states: Any) -> datetime:
    timestamps = [getattr(state, "last_updated", None) for state in states]
    aware = [value for value in timestamps if isinstance(value, datetime)]
    if aware:
        return min(aware)
    return datetime.now(UTC)


def _number(state: Any) -> float | None:
    if state is None:
        return None
    value = getattr(state, "state", state)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _unit(state: Any) -> str:
    return str(getattr(state, "attributes", {}).get("unit_of_measurement", "")).lower()


def _parse_soc(state: Any) -> float | None:
    value = _number(state)
    if value is None:
        return None
    if _unit(state) in {"%", "percent", "percentage"} or value > 1:
        return value / 100 if 0 <= value <= 100 else None
    return value if 0 <= value <= 1 else None


def _parse_percent(state: Any) -> float | None:
    value = _number(state)
    if value is None:
        return None
    if _unit(state) not in {"", "%", "percent", "percentage"}:
        return None
    return value if 0 <= value <= 100 else None


def _parse_energy_kwh(state: Any) -> float | None:
    value = _number(state)
    if value is None:
        return None
    unit = _unit(state)
    if unit in {"wh", "watt-hour", "watt hours"}:
        return value / 1000
    if unit in {"kwh", "kilowatt-hour", "kilowatt hours", ""}:
        return value
    return None


def _optional_power_kw(state: Any | None) -> float | None:
    if state is None:
        return None
    value = _number(state)
    if value is None:
        return None
    unit = _unit(state)
    if unit in {"w", "watt", "watts", ""}:
        return value / 1000
    if unit in {"kw", "kilowatt", "kilowatts"}:
        return value
    return None
