# Home Assistant Energy Planner

A Home Assistant integration and dashboard card for understanding
electricity prices, planning appliance operation, and safely optimising battery
grid charging.

## Status

The current release normalizes hourly and higher-resolution price data, exposes
an adjusted price timeline, and publishes appliance and battery-charge
recommendations. The latest recommendation is also visible in Home Assistant's
native Calendar view. The dependency-free Lovelace card is distributed as a
separate Marketplace Dashboard package and remains plan-only for ordinary
requests.

The project is structured as a clean, reusable HACS package. It intentionally contains no
household configuration, credentials, device identifiers, or provider account
data.

## Included capabilities

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
The [adapter architecture](docs/architecture.md) describes the provider,
tariff, battery, solar, profile, history, notification, and execution
boundaries.

## Current installation (development)

1. Copy `custom_components/energy_planner` into your Home Assistant
   `config/custom_components` folder.
2. Restart Home Assistant.
3. Add **Energy Planner** from **Settings → Devices & services**.
4. Select the hourly price sensor, tariff settings, fixed monthly cost, and
   optional battery/Forecast.Solar sources. Fixed monthly costs stay separate
   from hourly scheduling prices.
5. Install [Energy Planner Card](https://github.com/borgcube/lovelace-energy-planner-card)
   from the Marketplace Dashboard section, then reload your browser.

Updating the backend integration may require a Home Assistant restart. Updating
the standalone dashboard card only requires a browser reload, so chart and
presentation changes can be delivered independently.

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
explicitly `execution_mode: plan_only`. When optional Enphase-compatible
entities and a Forecast.Solar entry are configured, the response also includes
battery headroom and forecast context. Missing optional sources retain a safe
`price_only` fallback.

The separate **Energy Planner Card** dashboard package presents a compact chart
of the adjusted or spot price timeline, fixed monthly estimate, model status,
latest plan, and a collapsed plan-only appliance form. It is read-only with
respect to devices: submitting the form calls the existing plan service and
never starts an appliance.
Add it to a dashboard using the generated entity IDs:

```yaml
type: custom:energy-planner-card
price_sensor: sensor.energy_planner_adjusted_electricity_price
fixed_cost_sensor: sensor.energy_planner_fixed_monthly_electricity_cost
last_plan_sensor: sensor.energy_planner_last_plan
history_sensor: sensor.energy_planner_plan_history
price_mode: all_in
```

The **Last plan** sensor mirrors the latest appliance or battery plan response
in the normal Home Assistant entity UI. Its state is the plan status and its
attributes include the proposed window, cost, saving, source resolution, and
model status. The **Plan history** sensor retains a bounded history across
restarts, and **Appliance profiles** exposes saved runtime, power, and
execution definitions to dashboards and automations.

The **Plan schedule** calendar exposes that same latest recommendation as a
calendar event with its proposed window, cost, saving, and price-source details.
These native entities provide the dashboard-facing data contract. The card
shows up to 192 timeline points and remains useful when only price data is
available.

### Migrating from the bundled card

Older integration releases registered `/energy_planner/energy-planner-card.js`
automatically. After installing the standalone card, remove that legacy URL
from **Settings → Dashboards → Resources** if it is still present, keep the
existing `custom:energy-planner-card` YAML, and reload the browser. The backend
still serves the legacy path for dashboards that explicitly configured it, but
new card installs should use the Marketplace Dashboard package so frontend
updates do not require an integration restart.

`energy_planner.save_appliance_profile` stores a reusable profile, and
`energy_planner.plan_appliance_profile` can run it in `plan_only` mode or
deliver a persistent notification at the planned start. Automatic mode is
fail-closed: it requires an enabled profile, an explicit verified native
programme/delayed-start service, a power-monitoring entity, fresh plan data,
and a load that is not already running. Generic switch/light activation,
missing or stale inputs, an expired deadline, or an active load blocks the
action. Power monitoring can block or confirm a start; it never authorizes one.
