"""Composable electricity import-cost models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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

    def import_price(self, spot_price_per_kwh: float, at: datetime) -> float:
        """Return the variable all-in cost used for scheduling decisions."""
        del at
        return spot_price_per_kwh + self.supplier_markup + self.variable_grid_cost

    def fixed_monthly_cost(self) -> float:
        """Return the monthly estimate without distorting hourly decisions."""
        return self.monthly_fixed_cost
