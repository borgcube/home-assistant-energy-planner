"""Stable internal contracts between Energy Planner modules.

Provider-specific code belongs behind these ports. Planning and presentation
code consume the normalized models and must never depend on an Enphase,
Forecast.Solar, ENTSO, or supplier-specific entity shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .pricing import PriceTimeline


@runtime_checkable
class PriceProviderAdapter(Protocol):
    """Convert one electricity-price provider's attributes into a timeline."""

    key: str

    def supports(self, attributes: dict[str, Any]) -> bool:
        """Return whether this adapter understands the supplied attributes."""

    def normalize(self, attributes: dict[str, Any]) -> PriceTimeline:
        """Return normalized spot prices in EUR/kWh."""


@runtime_checkable
class CostModel(Protocol):
    """Convert a spot price into an import decision price and bill estimate."""

    key: str

    def import_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the variable all-in import price for one time slot."""

    def export_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the value credited for one exported kWh."""

    def fixed_monthly_cost(self) -> float:
        """Return the separate recurring monthly electricity cost."""


@runtime_checkable
class BatteryAdapter(Protocol):
    """Provide a vendor-neutral battery snapshot for the optimiser."""

    key: str

    async def async_snapshot(self) -> BatterySnapshot | None:
        """Return the latest battery state, or None when unavailable."""


@runtime_checkable
class SolarForecastAdapter(Protocol):
    """Provide a vendor-neutral solar forecast for the optimiser."""

    key: str

    async def async_forecast(self) -> SolarForecast | None:
        """Return the current production forecast, or None when unavailable."""


@dataclass(frozen=True, slots=True)
class BatterySnapshot:
    """Battery state consumed by the optimiser, independent of its vendor."""

    captured_at: datetime
    state_of_charge: float
    usable_capacity_kwh: float
    reserve_percent: float
    charging_power_kw: float | None = None
    discharging_power_kw: float | None = None


@dataclass(frozen=True, slots=True)
class SolarForecastPoint:
    """Expected production over one scheduled time window."""

    start_time: datetime
    end_time: datetime
    energy_kwh: float


@dataclass(frozen=True, slots=True)
class SolarForecast:
    """Vendor-neutral forecast produced by Forecast.Solar or another source."""

    generated_at: datetime
    points: tuple[SolarForecastPoint, ...]
