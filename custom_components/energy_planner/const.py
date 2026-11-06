"""Constants for the Energy Planner integration."""

from typing import Final

DOMAIN: Final = "energy_planner"
PLANNER_NAME: Final = "Energy Planner"

CONF_PRICE_ENTITY: Final = "price_entity"
CONF_SUPPLIER_MARKUP: Final = "supplier_markup"
CONF_VARIABLE_GRID_COST: Final = "variable_grid_cost"
CONF_FIXED_MONTHLY_COST: Final = "fixed_monthly_cost"

DEFAULT_SUPPLIER_MARKUP: Final = 0.0
DEFAULT_VARIABLE_GRID_COST: Final = 0.0
DEFAULT_FIXED_MONTHLY_COST: Final = 0.0

ATTR_DATA: Final = "data"
ATTR_SOURCE_ENTITY: Final = "source_entity"
ATTR_MODEL_STATUS: Final = "model_status"
ATTR_FIXED_MONTHLY_COST: Final = "fixed_monthly_cost"
ATTR_CURRENT_SPOT_PRICE: Final = "current_spot_price"
ATTR_CURRENT_ALL_IN_PRICE: Final = "current_all_in_price"
ATTR_LAST_UPDATED: Final = "last_updated"

MODEL_STATUS_PRICE_ONLY: Final = "price_only"
MODEL_STATUS_UNAVAILABLE: Final = "unavailable"
