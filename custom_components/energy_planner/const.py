"""Constants for the Energy Planner integration."""

from typing import Final

DOMAIN: Final = "energy_planner"
PLANNER_NAME: Final = "Energy Planner"

CONF_PRICE_ENTITY: Final = "price_entity"
CONF_SUPPLIER_MARKUP: Final = "supplier_markup"
CONF_VARIABLE_GRID_COST: Final = "variable_grid_cost"
CONF_FIXED_MONTHLY_COST: Final = "fixed_monthly_cost"
CONF_TARIFF_MODE: Final = "tariff_mode"
CONF_TOU_PEAK_GRID_COST: Final = "tou_peak_grid_cost"
CONF_TOU_OFFPEAK_GRID_COST: Final = "tou_offpeak_grid_cost"
CONF_TOU_PEAK_START_HOUR: Final = "tou_peak_start_hour"
CONF_TOU_PEAK_END_HOUR: Final = "tou_peak_end_hour"
CONF_EXPORT_RATE: Final = "export_rate"
CONF_BATTERY_SOC_ENTITY: Final = "battery_soc_entity"
CONF_BATTERY_CAPACITY_ENTITY: Final = "battery_capacity_entity"
CONF_BATTERY_CHARGE_POWER_ENTITY: Final = "battery_charge_power_entity"
CONF_BATTERY_DISCHARGE_POWER_ENTITY: Final = "battery_discharge_power_entity"
CONF_BATTERY_RESERVE_PERCENT: Final = "battery_reserve_percent"
CONF_FORECAST_SOLAR_ENTRY: Final = "forecast_solar_entry"

DEFAULT_SUPPLIER_MARKUP: Final = 0.0
DEFAULT_VARIABLE_GRID_COST: Final = 0.0
DEFAULT_FIXED_MONTHLY_COST: Final = 0.0
DEFAULT_TARIFF_MODE: Final = "flat_rate"
DEFAULT_TOU_PEAK_GRID_COST: Final = 0.0
DEFAULT_TOU_OFFPEAK_GRID_COST: Final = 0.0
DEFAULT_TOU_PEAK_START_HOUR: Final = 7
DEFAULT_TOU_PEAK_END_HOUR: Final = 23
DEFAULT_EXPORT_RATE: Final = 0.0
DEFAULT_BATTERY_RESERVE_PERCENT: Final = 10.0

TARIFF_MODE_FLAT: Final = "flat_rate"
TARIFF_MODE_TIME_OF_USE: Final = "time_of_use"

ATTR_DATA: Final = "data"
ATTR_SOURCE_ENTITY: Final = "source_entity"
ATTR_MODEL_STATUS: Final = "model_status"
ATTR_FIXED_MONTHLY_COST: Final = "fixed_monthly_cost"
ATTR_CURRENT_SPOT_PRICE: Final = "current_spot_price"
ATTR_CURRENT_ALL_IN_PRICE: Final = "current_all_in_price"
ATTR_CURRENT_EXPORT_PRICE: Final = "current_export_price"
ATTR_LAST_UPDATED: Final = "last_updated"

MODEL_STATUS_PRICE_ONLY: Final = "price_only"
MODEL_STATUS_BATTERY_AWARE: Final = "battery_aware"
MODEL_STATUS_COMPLETE: Final = "complete"
MODEL_STATUS_UNAVAILABLE: Final = "unavailable"

EXECUTION_PLAN_ONLY: Final = "plan_only"
EXECUTION_NOTIFY_AT_START: Final = "notify_at_start"
EXECUTION_AUTOMATIC: Final = "automatic"

PLAN_STATUS_RECOMMENDED: Final = "recommended"
PLAN_STATUS_SCHEDULED: Final = "scheduled"
PLAN_STATUS_RUNNING: Final = "running"
PLAN_STATUS_COMPLETED: Final = "completed"
PLAN_STATUS_MISSED: Final = "missed"
PLAN_STATUS_UNAVAILABLE: Final = "unavailable"

STORAGE_VERSION: Final = 1
MAX_PLAN_HISTORY: Final = 50

SERVICE_PLAN_APPLIANCE: Final = "plan_appliance"
SERVICE_PLAN_BATTERY_CHARGE: Final = "plan_battery_charge"
SERVICE_SAVE_APPLIANCE_PROFILE: Final = "save_appliance_profile"
SERVICE_REMOVE_APPLIANCE_PROFILE: Final = "remove_appliance_profile"
SERVICE_PLAN_APPLIANCE_PROFILE: Final = "plan_appliance_profile"
SERVICE_APPLIANCE_ID: Final = "appliance_id"
SERVICE_PROFILE_ID: Final = "profile_id"
SERVICE_PROFILE_NAME: Final = "name"
SERVICE_DURATION_MINUTES: Final = "duration_minutes"
SERVICE_DEADLINE: Final = "deadline"
SERVICE_EARLIEST_START: Final = "earliest_start"
SERVICE_AVERAGE_POWER_KW: Final = "average_power_kw"
SERVICE_ENERGY_ENTITY: Final = "energy_entity"
SERVICE_CHARGE_POWER_KW: Final = "charge_power_kw"
SERVICE_ENTRY_ID: Final = "entry_id"
SERVICE_EXECUTION_MODE: Final = "execution_mode"
SERVICE_START_ENTITY: Final = "start_entity"
SERVICE_START_SERVICE: Final = "start_service"
SERVICE_SERVICE_DATA: Final = "service_data"
SERVICE_VERIFIED_DELAYED_START: Final = "verified_delayed_start"
SERVICE_ENABLED: Final = "enabled"
SERVICE_POWER_ENTITY: Final = "power_entity"
SERVICE_POWER_THRESHOLD_W: Final = "power_threshold_w"
SERVICE_LOAD_GROUP: Final = "load_group"
