# Adapter architecture

Energy Planner keeps external integrations behind small internal contracts so
the planning engine and dashboard do not contain supplier- or vendor-specific
logic. The current release is deliberately read-only: it provides normalized
price data, cost calculations, plan responses, a Last Plan sensor, and a native
calendar entity, and a read-only native Lovelace card. The storage and profile
models are internal foundations; notifications, battery/solar optimisation,
and device execution are not APIs shipped by this release.

## Contracts

| Contract | Supplies | Initial implementation |
| --- | --- | --- |
| `PriceProviderAdapter` | A normalized hourly spot-price timeline | `EntsoDynamicPricesAdapter`, then generic fallback |
| `CostModel` | Variable all-in import price and fixed monthly cost | `FlatRateCostModel` |
| `BatteryAdapter` | `BatterySnapshot` | Planned Enphase adapter |
| `SolarForecastAdapter` | `SolarForecast` | Planned Forecast.Solar adapter |

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

Regional tariffs can implement a different `CostModel` for time-of-use fees,
percentages, taxes, export compensation, or a supplier's special formula.

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

A future card enhancement may add available battery/solar context. The card
must remain useful with price-only data while optional inputs are unavailable.

The versioned storage boundary records the latest plan, a bounded plan history,
and appliance profile data through Home Assistant's storage facility. This is
an internal persistence model, not a public history service or a promise that
every historical record is exposed as an entity.

## Profiles and notifications

The profile model stores a display name, expected runtime, power-monitoring
entity, finish-by inputs, simultaneous-load group, execution mode, and the
verified native start action required for automatic mode. Current plan services
still receive requests directly; no public profile-management API is promised
until profile lifecycle wiring is complete.

Notifications are also not implemented. A future notify-at-start mode may send
the recommendation to the household, but notification delivery must remain
separate from automatic execution and must not be inferred from a generic
switch or power sensor.

## Planning engine

`planning.py` is independent of Home Assistant entities and device-control
services. It receives a normalized `PriceTimeline` plus an
`AppliancePlanRequest` and returns the least-cost contiguous window that fits
the requested duration and deadline. This is the shared scheduling primitive
for the current plan-only flow and any future notification or automatic modes;
those additional modes are not implemented yet.

No current scheduling primitive can turn on an appliance. If automatic
execution is implemented later, it must be guarded by all of these conditions:

- the appliance has an individually enabled profile and an explicitly selected
  automatic mode;
- the controller adapter exposes a verified, device-specific native
  programme-start or delayed-start action;
- the price data is present and fresh, the plan is still enabled, and its
  deadline has not passed; and
- the device is not already running and the load-group constraints still hold.

Missing or stale inputs, an expired or disabled plan, an unavailable verified
action, a generic switch-only integration, or an already-running device must
cancel automatic execution. Power monitoring may confirm a start or improve
future estimates, but it is never permission to start a programme. Every
future action should be observable in Home Assistant's logbook.
