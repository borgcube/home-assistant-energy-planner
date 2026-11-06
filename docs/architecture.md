# Adapter architecture

Energy Planner keeps external integrations behind small internal contracts so
the planning engine and dashboard do not contain supplier- or vendor-specific
logic.

## Contracts

| Contract | Supplies | Initial implementation |
| --- | --- | --- |
| `PriceProviderAdapter` | A normalized hourly spot-price timeline | `GenericHourlyPriceAdapter` |
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

The generic adapter supports three widespread formats: `data`,
`hourly_prices`, and `prices`. It is intentionally the fallback rather than a
dependency of the planner.

## Cost models

`FlatRateCostModel` is the initial model for a variable market price plus a
supplier markup and variable grid/tax cost. Fixed monthly costs are returned
separately so a monthly charge never biases an hourly scheduling decision.

Regional tariffs can implement a different `CostModel` for time-of-use fees,
percentages, taxes, export compensation, or a supplier's special formula.
