"""Composable electricity import- and export-cost models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any


@dataclass(frozen=True, slots=True)
class FlatRateCostModel:
    """Add configured variable costs to market price and keep fixed costs separate.

    This is the initial Dutch dynamic-tariff model. Other providers can add a
    model that applies time-of-use fees, percentages, taxes, or rebates without
    affecting price adapters, planning logic, or the Lovelace card.
    """

    supplier_markup: float
    variable_grid_cost: float
    monthly_fixed_cost: float
    key: str = "flat_rate"
    export_compensation: float = 0.0

    def import_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the variable all-in cost used for scheduling decisions."""
        del at
        return spot_price_per_kwh + self.supplier_markup + self.variable_grid_cost

    def fixed_monthly_cost(self) -> float:
        """Return the monthly estimate without distorting hourly decisions."""
        return self.monthly_fixed_cost

    def export_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the configured credit for one exported kWh."""
        del at
        return spot_price_per_kwh + self.export_compensation


@dataclass(frozen=True, slots=True)
class TimeOfUseCostModel:
    """Apply different variable import costs during peak and off-peak hours.

    ``peak_start`` is inclusive and ``peak_end`` is exclusive.  An interval
    whose start is later than its end crosses midnight, which allows schedules
    such as 22:00--07:00.  ``export_compensation`` is an additional amount per
    exported kWh, so a positive value increases the returned export value and a
    negative value represents an export fee.
    """

    peak_markup: float
    off_peak_markup: float
    monthly_fixed_cost: float
    peak_start: time
    peak_end: time
    export_compensation: float = 0.0
    key: str = "time_of_use"

    def __post_init__(self) -> None:
        """Reject ambiguous schedules while allowing overnight intervals."""
        if self.peak_start == self.peak_end:
            raise ValueError("peak_start and peak_end must be different")

    def import_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the variable all-in import price for the scheduled period."""
        markup = self.peak_markup if self._is_peak(at.time()) else self.off_peak_markup
        return spot_price_per_kwh + markup

    def export_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the value credited for one exported kWh.

        Export compensation is currently schedule-independent, but ``at`` is
        accepted to keep this method interchangeable with future tariff models.
        """
        del at
        return spot_price_per_kwh + self.export_compensation

    def fixed_monthly_cost(self) -> float:
        """Return the monthly estimate separately from hourly prices."""
        return self.monthly_fixed_cost

    def _is_peak(self, at: time) -> bool:
        """Return whether a wall-clock time falls in the peak interval."""
        if self.peak_start < self.peak_end:
            return self.peak_start <= at < self.peak_end
        return at >= self.peak_start or at < self.peak_end


def build_cost_model(
    config: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> FlatRateCostModel | TimeOfUseCostModel:
    """Build a cost model from tariff settings, defaulting to flat rate.

    The flat-rate defaults intentionally match the original model's neutral
    values.  Keyword overrides are useful to callers that already have typed
    settings, while a mapping keeps this builder convenient for configuration
    data from Home Assistant.
    """
    settings = dict(config or {})
    settings.update(overrides)
    tariff = settings.pop("tariff", settings.pop("type", "flat_rate"))

    if tariff in ("flat", "flat_rate"):
        return FlatRateCostModel(
            supplier_markup=float(settings.pop("supplier_markup", 0.0)),
            variable_grid_cost=float(settings.pop("variable_grid_cost", 0.0)),
            monthly_fixed_cost=float(settings.pop("monthly_fixed_cost", 0.0)),
            export_compensation=float(
                settings.pop("export_compensation", settings.pop("export_rate", 0.0))
            ),
        )
    if tariff not in ("time_of_use", "tou"):
        raise ValueError(f"Unsupported tariff type: {tariff}")

    return TimeOfUseCostModel(
        peak_markup=float(settings.pop("peak_markup", settings.pop("peak_cost", 0.0))),
        off_peak_markup=float(
            settings.pop("off_peak_markup", settings.pop("off_peak_cost", 0.0))
        ),
        monthly_fixed_cost=float(settings.pop("monthly_fixed_cost", 0.0)),
        peak_start=_as_time(settings.pop("peak_start", "07:00")),
        peak_end=_as_time(settings.pop("peak_end", "23:00")),
        export_compensation=float(settings.pop("export_compensation", 0.0)),
    )


def _as_time(value: time | str) -> time:
    """Normalize a schedule boundary supplied as a time or HH:MM string."""
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError as err:
            raise ValueError(f"Invalid tariff schedule time: {value}") from err
    raise TypeError("Tariff schedule times must be datetime.time or HH:MM strings")
