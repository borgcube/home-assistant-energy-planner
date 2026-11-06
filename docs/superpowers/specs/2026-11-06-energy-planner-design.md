# Energy Planner and Dashboard Card — Design

## Purpose

Provide a Home Assistant energy-planning system and dashboard card that make
hourly electricity costs understandable and turn that information into safe,
actionable recommendations. The first release supports grid-charging guidance
for Enphase batteries and a calendar-style plan for opted-in appliances.

The system uses the existing ENTSO Dynamic Prices integration as the source of
hourly spot prices. It does not fetch the electricity market API separately.

## Goals

- Show spot price and adjusted, variable all-in import price side by side.
- Show fixed monthly charges separately as a bill estimate.
- Recommend battery grid-charging windows using Enphase battery state and
  Forecast.Solar production when those sources are available.
- Fall back safely to grid-price-only recommendations if battery or solar data
  is unavailable.
- Provide a calendar-like appliance planning interface with least-cost start
  windows, deadlines, duration, expected cost, and expected saving.
- Permit automatic operation only for individually opted-in devices with a
  proven, device-specific programme-start or delayed-start capability.

## Non-goals for the first release

- Replacing the ENTSO integration or retrieving market data directly.
- Treating a generic power switch as a safe way to start an appliance.
- Automatically scheduling an appliance merely because it has power monitoring.
- Predicting a household's total load profile beyond the configured devices and
  available production/battery inputs.

## Architecture

### 1. Data adapters and internal contracts

Adapters convert source entities into a common hourly model:

`spot price -> variable all-in import price -> solar forecast -> battery state -> recommendation`

- The ENTSO hourly data is normalized to hourly timestamps and EUR/kWh.
- Every provider is an interchangeable `PriceProviderAdapter`; pricing logic
  consumes its vendor-neutral hourly timeline rather than provider attributes.
- Configured variable cost components are applied to each hourly spot price.
- Fixed monthly values remain separate from the hourly decision price.
- Every battery and solar source is an interchangeable `BatteryAdapter` or
  `SolarForecastAdapter`. Forecast.Solar and Enphase are initial adapters, not
  dependencies of the planner.
- A `CostModel` owns provider- and tariff-specific import/export calculations.
  The initial flat-rate model can be replaced with time-of-use, percentage, or
  regional tax models without changing the optimiser or card.

### 2. Planner

The planner runs inside Home Assistant, independently of the dashboard browser.
It recalculates when price data, forecasts, battery state, appliance plans, or
relevant configuration changes.

It publishes Home Assistant entities for the card and automations, including:

- current spot price and all-in import price;
- fixed-charge estimate;
- best battery charging window and reason;
- appliance recommendation, proposed start/end, cost, and saving;
- plan state: recommended, scheduled, waiting for you, running, completed,
  missed, or unavailable;
- model status: complete or price-only fallback; and
- calculation timestamp.

### 3. Scheduling safeguards

Each appliance has an explicit profile and a separate execution mode:

- **Plan only**: record and display a recommended window.
- **Notify at start**: notify the household at the recommended start time.
- **Automatic**: only for a device with a verified native programme-start or
  delayed-start service/action, and only after explicit opt-in.

Power monitoring confirms whether a planned appliance actually started and may
improve future duration estimates. It is never treated as authorization or a
mechanism to start a programme.

An automatic action is cancelled if the profile or plan is disabled, the
deadline passes, or the device is already running.

### 4. Dashboard card

The custom Home Overview card presents a 24–48 hour calendar-style timeline:

- hourly all-in prices, colour-coded by relative cost;
- spot and all-in values together;
- current fixed-cost monthly estimate;
- battery and solar context, when present;
- recommendations and their reasons; and
- appliance plan blocks with planned time, cost, saving, deadline, and state.

The card shows the model status and refresh time. When inputs are incomplete,
it remains useful by showing the price timeline and price-only guidance.

## Configuration

Home Assistant helpers provide editable configuration without code changes.

### Cost configuration

- Supplier markup and each variable per-kWh import component.
- Tax/VAT treatment and other variable adjustments.
- Fixed electricity delivery charge, network-management charge, and tax credit
  for the monthly bill estimate.
- Separate import and export/feed-in treatment where required.

The provider's example charges establish the distinction to preserve:

- Electricity delivery: EUR 8.50 per month.
- Other monthly standing charges include network-management cost and energy-tax
  reduction.
- These fixed costs are displayed separately; they are not added to hourly
  scheduling prices.

### Battery configuration

- Enphase entity mappings.
- Usable capacity, charge/discharge limits, and minimum reserve.
- Forecast.Solar entity mapping.

If Enphase or Forecast.Solar is missing or stale, the planner uses the adjusted
grid-price curve alone and labels the result as price-only.

### Appliance profile configuration

- Display name.
- Power-monitoring entity.
- Expected runtime.
- Finish-by deadline.
- Maximum simultaneous-load group or limit.
- Execution mode.
- Verified native programme-start/delayed-start action, mandatory for Automatic
  mode.

## Reliability and observability

- Missing or stale ENTSO price data prevents automatic scheduling and produces
  an explicit unavailable status.
- Missing solar/battery data triggers only the documented price-only fallback.
- Schedule conflicts are visible in the calendar and resolved before actions
  are scheduled.
- Every calculation, recommendation, schedule, cancellation, and automatic
  device action is written to the Home Assistant logbook.

## Validation

- Unit tests: price normalization, all-in price calculation, fixed-cost
  calculation, battery/solar fallback, deadline selection, and conflict
  handling.
- Safety tests: disabled profiles, expired deadlines, already-running devices,
  absent native programme-start action, and stale price data.
- Runtime checks: card displays a usable price timeline before forecast/battery
  inputs arrive; price-only recommendations work; an opted-in test appliance
  schedules only through its verified native action.

## Delivery sequence

1. Normalize ENTSO prices and create configurable all-in/fixed-cost entities.
2. Build the read-only price timeline and bill-estimate portion of the card.
3. Add price-only battery and appliance recommendations.
4. Add Forecast.Solar and Enphase-aware optimisation.
5. Add appliance calendar planning and notifications.
6. Add automatic operation for individually verified appliance profiles.
