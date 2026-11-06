# Adapter architecture

Energy Planner keeps external integrations behind small internal contracts so
the planning engine and dashboard do not contain supplier- or vendor-specific
logic. The integration exposes normalized price data, tariff calculations,
provider context, persistent plan history, profiles, notifications, a native
calendar, and a dashboard card. Device execution remains opt-in and fail-closed.

## Contracts

| Contract | Supplies | Initial implementation |
| --- | --- | --- |
| `PriceProviderAdapter` | A normalized hourly spot-price timeline | `EntsoDynamicPricesAdapter`, then generic fallback |
| `CostModel` | Variable all-in import/export price and fixed monthly cost | `FlatRateCostModel`, `TimeOfUseCostModel` |
| `BatteryAdapter` | `BatterySnapshot` | `EnphaseBatteryAdapter` |
| `SolarForecastAdapter` | `SolarForecast` | `ForecastSolarAdapter` |

The optimiser will only consume the normalized types. A provider integration
must therefore add an adapter, not special cases to the calendar card or
scheduling engine.

## Adding a price provider

Implement `PriceProviderAdapter` in `custom_components/energy_planner`:

1. Give it a stable `key`.
2. Make `supports(attributes)` identify only its provider's data shape.
3. Make `normalize(attributes)` return `PriceTimeline` with timezone-aware
   `PricePoint` values in EUR/kWh.
4. Register it before the generic adapter in `DEFAULT_PRICE_ADAPTERS`.
5. Add tests for correct conversion and for malformed provider data.

The ENTSO adapter supports the actual `prices_today` and `prices_tomorrow`
attributes with `time` and `price` fields. The generic fallback supports three
widespread formats: `data`,
`hourly_prices`, and `prices`. It is intentionally the fallback rather than a
dependency of the planner.

## Cost models

`FlatRateCostModel` is the initial model for a variable market price plus a
supplier markup and variable grid/tax cost. Fixed monthly costs are returned
separately so a monthly charge never biases an hourly scheduling decision.

`TimeOfUseCostModel` supports peak/off-peak schedules, overnight boundaries,
export compensation, and the same separate fixed monthly charge. The config
flow defaults existing entries to the flat model, so upgrading does not change
old calculations.

Enphase battery and Forecast.Solar adapters normalize optional source data, but
they are not an automatic-control path. Their absence or stale data must retain
the price-only fallback; neither adapter may silently authorize device
execution.

## Dashboard, persistence, and history

The current dashboard-facing contract is the adjusted price sensor's `data`
attribute, the Last Plan sensor, and the Plan schedule calendar. The included
`www/energy-planner-card.js` renders those entities as a native Lovelace card
with a 24–48 hour timeline, model status, fixed-cost summary, latest plan, and
a plan-only request form. It does not expose a device-control API.

The coordinator adds optional battery/solar context to the model status and
the native Battery context and Solar forecast sensors. The card remains useful
with price-only data while optional inputs are unavailable.

The versioned storage boundary records the latest plan, a bounded plan history,
and appliance profile data through Home Assistant's storage facility. This is
an internal persistence model, not a public history service or a promise that
every historical record is exposed as an entity.

## Profiles, notifications, and guarded execution

The profile model stores a display name, expected runtime, power-monitoring
entity, simultaneous-load group, execution mode, and the verified native start
action required for automatic mode. `save_appliance_profile`,
`remove_appliance_profile`, and `plan_appliance_profile` expose that lifecycle
through Home Assistant services. Direct plan actions remain plan-only.

`notify_at_start` schedules a persistent Home Assistant notification and never
controls a device. Scheduled plans are stored and re-armed after restart.
Automatic mode is only accepted when the profile is enabled, explicitly marked
as verified, names a native delayed-start/programme service, and has a power
monitor. Generic immediate switch/light activation is rejected. At run time,
missing prices, an expired deadline, unknown power, or an already active load
blocks the call. Power monitoring is a safety interlock, not authorization.

## Planning engine

`planning.py` is independent of Home Assistant entities and device-control
services. It receives a normalized `PriceTimeline` plus an
`AppliancePlanRequest` and returns the least-cost contiguous window that fits
the requested duration and deadline. This is the shared scheduling primitive
for plan-only, notification, and guarded profile execution modes; it never
performs a device call itself.

No scheduling primitive turns on an appliance directly. Automatic execution is
guarded by all of these conditions:

- the appliance has an individually enabled profile and an explicitly selected
  automatic mode;
- the controller adapter exposes a verified, device-specific native
  programme-start or delayed-start action;
- the price data is present and fresh, the plan is still enabled, and its
  deadline has not passed; and
- the device is not already running and the load-group constraints still hold.

Missing or stale inputs, an expired or disabled plan, an unavailable verified
action, a generic switch-only integration, or an already-running device
cancels automatic execution. Power monitoring may confirm a start or improve
future estimates, but it is never permission to start a programme. Scheduled
state transitions are visible in the native Last plan and calendar entities.
