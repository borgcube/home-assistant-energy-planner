# Home Assistant Energy Planner

A planned Home Assistant integration and dashboard card for understanding
electricity prices, planning appliance operation, and safely optimising battery
grid charging.

## Status

Foundation implementation in progress. The current slice normalizes hourly
price data, exposes an adjusted price timeline, and publishes a read-only
cheapest upcoming one-hour recommendation. Battery optimisation, dashboard
work, calendar planning, and appliance control follow in later slices.

The project is being structured as a clean, reusable package for eventual HACS
and Home Assistant Marketplace submission. It intentionally contains no
household configuration, credentials, device identifiers, or provider account
data.

## Planned capabilities

- Hourly spot and configurable all-in import price timeline.
- Fixed-cost monthly bill estimate.
- Enphase battery and Forecast.Solar-aware recommendations, with safe
  price-only fallback.
- Calendar-style appliance plans with deadlines, cost, and estimated savings.
- Automatic operation only for explicitly opted-in devices with a verified
  programme-start or delayed-start capability.

See [the design specification](docs/superpowers/specs/2026-11-06-energy-planner-design.md)
for the agreed scope and safeguards.
The [adapter architecture](docs/architecture.md) describes how providers,
cost models, batteries, and solar forecasts remain replaceable.

## Current installation (development)

1. Copy `custom_components/energy_planner` into your Home Assistant
   `config/custom_components` folder.
2. Restart Home Assistant.
3. Add **Energy Planner** from **Settings → Devices & services**.
4. Select the hourly price sensor and enter only the variable per-kWh costs.
   Fixed monthly costs are kept separate for the bill estimate.

The resulting `sensor.energy_planner_adjusted_electricity_price` exposes an
hourly `data` attribute. Every entry includes `start_time`, `end_time`,
`spot_price_per_kwh`, and adjusted `price_per_kwh` values.

The integration also creates `sensor.energy_planner_cheapest_1_hour_price_window`.
Its timestamp is the start of the cheapest complete one-hour window in the
next 24 hours; attributes include the end time, average price, source, and
`model_status: price_only`. It is a recommendation only and does not control
any device.
