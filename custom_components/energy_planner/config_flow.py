"""Config flow for Energy Planner."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_FIXED_MONTHLY_COST,
    CONF_PRICE_ENTITY,
    CONF_SUPPLIER_MARKUP,
    CONF_VARIABLE_GRID_COST,
    DEFAULT_FIXED_MONTHLY_COST,
    DEFAULT_SUPPLIER_MARKUP,
    DEFAULT_VARIABLE_GRID_COST,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the editable configuration schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_PRICE_ENTITY,
                default=defaults.get(CONF_PRICE_ENTITY),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_SUPPLIER_MARKUP,
                default=defaults.get(CONF_SUPPLIER_MARKUP, DEFAULT_SUPPLIER_MARKUP),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-1, max=5, step=0.0001, mode="box")
            ),
            vol.Required(
                CONF_VARIABLE_GRID_COST,
                default=defaults.get(
                    CONF_VARIABLE_GRID_COST, DEFAULT_VARIABLE_GRID_COST
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-1, max=5, step=0.0001, mode="box")
            ),
            vol.Required(
                CONF_FIXED_MONTHLY_COST,
                default=defaults.get(
                    CONF_FIXED_MONTHLY_COST, DEFAULT_FIXED_MONTHLY_COST
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-500, max=500, step=0.01, mode="box")
            ),
        }
    )


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
