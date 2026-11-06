"""Config flow for Energy Planner."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    DEFAULT_FIXED_MONTHLY_COST,
    DEFAULT_SUPPLIER_MARKUP,
    DEFAULT_TARIFF_MODE,
    DEFAULT_TOU_OFFPEAK_GRID_COST,
    DEFAULT_TOU_PEAK_END_HOUR,
    DEFAULT_TOU_PEAK_GRID_COST,
    DEFAULT_TOU_PEAK_START_HOUR,
    DEFAULT_VARIABLE_GRID_COST,
    DOMAIN,
    TARIFF_MODE_FLAT,
    TARIFF_MODE_TIME_OF_USE,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the editable configuration schema."""
    defaults = defaults or {}
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_PRICE_ENTITY,
            default=defaults.get(CONF_PRICE_ENTITY),
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(
            CONF_SUPPLIER_MARKUP,
            default=defaults.get(CONF_SUPPLIER_MARKUP, DEFAULT_SUPPLIER_MARKUP),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-1, max=5, step=0.001, mode="box")
        ),
        vol.Required(
            CONF_VARIABLE_GRID_COST,
            default=defaults.get(CONF_VARIABLE_GRID_COST, DEFAULT_VARIABLE_GRID_COST),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-1, max=5, step=0.001, mode="box")
        ),
        vol.Required(
            CONF_FIXED_MONTHLY_COST,
            default=defaults.get(CONF_FIXED_MONTHLY_COST, DEFAULT_FIXED_MONTHLY_COST),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-500, max=500, step=0.01, mode="box")
        ),
        vol.Required(
            CONF_TARIFF_MODE,
            default=defaults.get(CONF_TARIFF_MODE, DEFAULT_TARIFF_MODE),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[TARIFF_MODE_FLAT, TARIFF_MODE_TIME_OF_USE],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_TOU_PEAK_GRID_COST,
            default=defaults.get(CONF_TOU_PEAK_GRID_COST, DEFAULT_TOU_PEAK_GRID_COST),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-1, max=5, step=0.001, mode="box")
        ),
        vol.Required(
            CONF_TOU_OFFPEAK_GRID_COST,
            default=defaults.get(
                CONF_TOU_OFFPEAK_GRID_COST, DEFAULT_TOU_OFFPEAK_GRID_COST
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-1, max=5, step=0.001, mode="box")
        ),
        vol.Required(
            CONF_TOU_PEAK_START_HOUR,
            default=defaults.get(CONF_TOU_PEAK_START_HOUR, DEFAULT_TOU_PEAK_START_HOUR),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, step=1, mode="box")
        ),
        vol.Required(
            CONF_TOU_PEAK_END_HOUR,
            default=defaults.get(CONF_TOU_PEAK_END_HOUR, DEFAULT_TOU_PEAK_END_HOUR),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, step=1, mode="box")
        ),
        vol.Required(
            CONF_EXPORT_RATE,
            default=defaults.get(CONF_EXPORT_RATE, DEFAULT_EXPORT_RATE),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=-5, max=5, step=0.001, mode="box")
        ),
        vol.Required(
            CONF_BATTERY_RESERVE_PERCENT,
            default=defaults.get(
                CONF_BATTERY_RESERVE_PERCENT, DEFAULT_BATTERY_RESERVE_PERCENT
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, mode="box")
        ),
    }

    entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    )
    for key in (
        CONF_BATTERY_SOC_ENTITY,
        CONF_BATTERY_CAPACITY_ENTITY,
        CONF_BATTERY_CHARGE_POWER_ENTITY,
        CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    ):
        value = defaults.get(key)
        schema[vol.Optional(key, default=value) if value else vol.Optional(key)] = (
            entity_selector
        )

    forecast_entry = defaults.get(CONF_FORECAST_SOLAR_ENTRY)
    schema[
        vol.Optional(
            CONF_FORECAST_SOLAR_ENTRY,
            default=forecast_entry,
        )
    ] = selector.ConfigEntrySelector(
        selector.ConfigEntrySelectorConfig(integration="forecast_solar")
    )
    return vol.Schema(schema)


class EnergyPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Planner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure price input and price adjustments."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PRICE_ENTITY])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_PRICE_ENTITY], data=user_input
            )
        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Return the integration options flow."""
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Edit Energy Planner cost inputs."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
