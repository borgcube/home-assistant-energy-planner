# Home Assistant Energy Planner

A planned Home Assistant integration and dashboard card for understanding
electricity prices, planning appliance operation, and safely optimising battery
grid charging.

## Status

Design phase. No integration or card code has been implemented yet.

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
