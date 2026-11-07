"""Estimate appliance usage from Home Assistant energy statistics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

MIN_ACTIVE_ENERGY_KWH = 0.005


@dataclass(frozen=True, slots=True)
class ApplianceUsageEstimate:
    """A robust usage summary derived from cumulative energy statistics."""

    average_power_kw: float
    active_hours: float
    utilization_percent: float
    samples: int

    def as_dict(self) -> dict[str, float | int]:
        """Return the summary in the plan response shape."""
        return {
            "historical_average_power_kw": round(self.average_power_kw, 3),
            "historical_active_hours": round(self.active_hours, 2),
            "historical_utilization_percent": round(self.utilization_percent, 1),
            "historical_samples": self.samples,
        }


def estimate_usage_from_statistics(
    rows: Iterable[Mapping[str, Any]],
    *,
    unit: str,
    minimum_active_energy_kwh: float = MIN_ACTIVE_ENERGY_KWH,
) -> ApplianceUsageEstimate | None:
    """Estimate active power from cumulative energy statistics.

    Rows are expected to contain cumulative ``sum`` values and period start
    timestamps. Positive changes are treated as active usage; the median power
    across those periods avoids one unusually high cycle dominating the result.
    """
    ordered_rows = sorted(
        (
            parsed
            for row in rows
            if (parsed := _parse_row(row, unit)) is not None
        ),
        key=lambda row: row[0],
    )
    if len(ordered_rows) < 2:
        return None

    active_power: list[float] = []
    active_hours = 0.0
    observed_hours = 0.0
    previous_time, previous_sum = ordered_rows[0]
    for current_time, current_sum in ordered_rows[1:]:
        interval_hours = (current_time - previous_time).total_seconds() / 3600
        if interval_hours <= 0:
            previous_time, previous_sum = current_time, current_sum
            continue
        observed_hours += interval_hours
        delta_kwh = current_sum - previous_sum
        if delta_kwh >= 0 and delta_kwh >= minimum_active_energy_kwh:
            active_power.append(delta_kwh / interval_hours)
            active_hours += interval_hours
        # A meter reset establishes a new baseline. It must not be counted as
        # negative usage, but the next positive interval remains usable.
        previous_time, previous_sum = current_time, current_sum

    if not active_power or observed_hours <= 0:
        return None
    return ApplianceUsageEstimate(
        average_power_kw=median(active_power),
        active_hours=active_hours,
        utilization_percent=min(100.0, active_hours / observed_hours * 100),
        samples=len(active_power),
    )


async def async_estimate_appliance_usage(
    hass: Any,
    energy_entity: str,
    *,
    history_days: int = 30,
) -> dict[str, Any]:
    """Read recorder statistics and return a plan-ready usage summary."""
    from homeassistant.components.recorder.statistics import statistics_during_period
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.helpers.recorder import get_instance

    state = hass.states.get(energy_entity)
    unit = state.attributes.get("unit_of_measurement") if state else None
    if _energy_unit_multiplier(unit) is None:
        raise HomeAssistantError(
            f"{energy_entity} is not an energy sensor with a supported unit"
        )

    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(days=history_days)
    try:
        rows_by_entity = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start_time,
            end_time,
            {energy_entity},
            "hour",
            None,
            {"sum"},
        )
    except Exception as err:  # noqa: BLE001
        raise HomeAssistantError(
            f"Energy history is unavailable for {energy_entity}"
        ) from err

    estimate = estimate_usage_from_statistics(
        rows_by_entity.get(energy_entity, []),
        unit=unit,
    )
    if estimate is None:
        raise HomeAssistantError(
            f"No usable energy history is available for {energy_entity}"
        )
    return {
        "energy_entity": energy_entity,
        "usage_source": "energy_history",
        "history_days": history_days,
        **estimate.as_dict(),
    }


def _parse_row(row: Mapping[str, Any], unit: str) -> tuple[datetime, float] | None:
    """Parse one recorder row and normalize its cumulative sum to kWh."""
    timestamp = _parse_timestamp(row.get("start"))
    try:
        total = float(row.get("sum")) * (_energy_unit_multiplier(unit) or 0)
    except (TypeError, ValueError):
        return None
    if timestamp is None or total < 0:
        return None
    return timestamp, total


def _parse_timestamp(value: Any) -> datetime | None:
    """Normalize recorder timestamps to timezone-aware UTC datetimes."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, tz=UTC)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _energy_unit_multiplier(unit: str | None) -> float | None:
    """Return the multiplier needed to express an energy value in kWh."""
    normalized = str(unit or "").replace(" ", "").lower()
    return {
        "wh": 0.001,
        "w⋅h": 0.001,
        "kwh": 1.0,
        "kw⋅h": 1.0,
        "mwh": 1000.0,
    }.get(normalized)
