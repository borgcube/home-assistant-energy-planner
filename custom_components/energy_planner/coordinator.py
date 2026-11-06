"""Coordinator for normalizing Energy Planner source data."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FIXED_MONTHLY_COST,
    CONF_PRICE_ENTITY,
    CONF_SUPPLIER_MARKUP,
    CONF_VARIABLE_GRID_COST,
    DOMAIN,
)
from .cost_models import FlatRateCostModel
from .price_adapters import DEFAULT_PRICE_ADAPTERS
from .pricing import PricePoint, PriceTimeline

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
        self.last_plan: dict[str, Any] | None = None

    def set_last_plan(self, response: dict[str, Any]) -> None:
        """Publish the latest plan response to native Home Assistant entities."""
        self.last_plan = dict(response)
        self.async_update_listeners()

    async def _async_update_data(self) -> PriceTimeline:
        """Return a normalized adjusted price timeline from the source sensor."""
        source_entity = self.config_entry.options.get(
            CONF_PRICE_ENTITY, self.config_entry.data[CONF_PRICE_ENTITY]
        )
        state = self.hass.states.get(source_entity)
        if state is None:
            raise UpdateFailed(f"Price source {source_entity} is unavailable")

        markup = float(
            self.config_entry.options.get(
                CONF_SUPPLIER_MARKUP,
                self.config_entry.data[CONF_SUPPLIER_MARKUP],
            )
        )
        grid_cost = float(
            self.config_entry.options.get(
                CONF_VARIABLE_GRID_COST,
                self.config_entry.data[CONF_VARIABLE_GRID_COST],
            )
        )
        try:
            spot_timeline = DEFAULT_PRICE_ADAPTERS.select(state.attributes).normalize(
                state.attributes
            )
            cost_model = FlatRateCostModel(
                supplier_markup=markup,
                variable_grid_cost=grid_cost,
                monthly_fixed_cost=float(
                    self.config_entry.options.get(
                        CONF_FIXED_MONTHLY_COST,
                        self.config_entry.data[CONF_FIXED_MONTHLY_COST],
                    )
                ),
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
