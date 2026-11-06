# Home Assistant Energy Planner

A planned Home Assistant integration and dashboard card for understanding
electricity prices, planning appliance operation, and safely optimising battery
grid charging.

## Status

The current release normalizes hourly and higher-resolution price data, exposes
an adjusted price timeline, and publishes read-only appliance and battery-charge
recommendations. The latest recommendation is also visible in Home Assistant's
native Calendar view. A dependency-free, read-only native Lovelace card is
included under `www/energy-planner-card.js`; storage-backed history and profile
data are internal foundations, while notifications and device control are not
implemented.

The project is being structured as a clean, reusable package for eventual HACS
and Home Assistant Marketplace submission. It intentionally contains no
household configuration, credentials, device identifiers, or provider account
data.

## Planned capabilities

- Hourly spot and configurable all-in import price timeline.
- Fixed-cost monthly bill estimate.
- Enphase battery and Forecast.Solar-aware recommendations, with safe
  price-only fallback.
- Persistent plan history and state recovery across Home Assistant restarts.
- Appliance profiles with runtime, deadline, power-monitoring, load-group, and
  execution settings.
- Notifications at a recommended start time.
- Automatic operation only for explicitly opted-in devices with a verified
  programme-start or delayed-start capability.

See [the design specification](docs/superpowers/specs/2026-11-06-energy-planner-design.md)
for the agreed scope and safeguards.
The [adapter architecture](docs/architecture.md) describes the implemented
provider and cost-model boundaries, as well as the planned battery, solar,
profile, history, notification, and execution boundaries.

## Current installation (development)

1. Copy `custom_components/energy_planner` into your Home Assistant
   `config/custom_components` folder.
2. Restart Home Assistant.
3. Add **Energy Planner** from **Settings → Devices & services**.
4. Select the hourly price sensor and enter only the variable per-kWh costs.
   Fixed monthly costs are kept separate for the bill estimate.

The resulting **Adjusted electricity price** sensor exposes an hourly `data`
attribute. Every entry includes `start_time`, `end_time`, `spot_price_per_kwh`,
and adjusted `price_per_kwh` values. Home Assistant generates the exact entity
ID from the device and area name, so use the entity picker when referencing it.
The sensor also reports `resolution_minutes`, which reflects the source
cadence, including 15-minute ENTSO-E data.

The **Fixed monthly electricity cost** sensor exposes the configured recurring
charge in EUR. This value stays separate from hourly scheduling prices and is
reported with `billing_period: month`.

The integration also creates a **Cheapest 1-hour price window** timestamp
sensor. Its timestamp is the start of the cheapest complete one-hour window in
the next 24 hours; attributes include the end time, average price, source, and
`model_status: price_only`. It is a recommendation only and does not control
any device.

The `energy_planner.plan_appliance` action accepts an appliance label, a
duration in 15-minute increments, a finish-by deadline, and expected average
power. Its
response contains the least-cost contiguous window, estimated cost, and
estimated saving versus running at the current price. It is explicitly
`execution_mode: plan_only`; it does not call or schedule any device.

The `energy_planner.plan_battery_charge` action accepts a charge duration,
finish-by deadline, and expected charge power. Its response adds the target
energy estimate and uses the same high-resolution price timeline. It is also
explicitly `execution_mode: plan_only`: battery state, solar forecast, and
battery control are not used until their adapters are configured in a later
slice.

The included **Energy Planner** dashboard card presents the adjusted or spot
price timeline, fixed monthly estimate, model status, latest plan, and a
plan-only appliance form. It is read-only with respect to devices: submitting
the form calls the existing plan service and never starts an appliance.

The **Last plan** sensor mirrors the latest appliance or battery plan response
in the normal Home Assistant entity UI. Its state is the plan status and its
attributes include the proposed window, cost, saving, source resolution, and
model status. It is in-memory for now, so the latest plan is lost when Home
Assistant restarts; no history API is exposed yet.

The **Plan schedule** calendar exposes that same latest recommendation as a
calendar event with its proposed window, cost, saving, and price-source details.
These native entities provide the dashboard-facing data contract. The card
shows up to 48 timeline points and remains useful when only price data is
available.

All current planning remains `execution_mode: plan_only`: the services return a
recommendation and do not call, schedule, or turn on a device. Future profiles,
notifications, persistence, and automatic execution must be added behind
explicit contracts. Automatic execution is only acceptable for an individually
enabled profile with a verified native programme-start or delayed-start action;
a generic switch, power monitoring, stale or missing prices, an expired
deadline, a disabled plan, or an already-running device must never authorize
an automatic start.
