from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from energy_planner.battery_adapters import EnphaseBatteryAdapter
from energy_planner.solar_adapters import ForecastSolarAdapter


def state(value: str, unit: str, updated: datetime | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=value,
        attributes={"unit_of_measurement": unit},
        last_updated=updated,
    )


class States:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values

    def get(self, entity_id: str) -> object | None:
        return self.values.get(entity_id)


class Service:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict, dict]] = []

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))
        return self.response


def test_enphase_adapter_parses_and_converts_entities() -> None:
    captured = datetime.fromisoformat("2026-11-06T12:00:00+01:00")
    hass = SimpleNamespace(
        states=States(
            {
                "sensor.soc": state("82", "%", captured),
                "sensor.capacity": state("10240", "Wh", captured),
                "sensor.charge": state("2500", "W", captured),
                "sensor.reserve": state("20", "%", captured),
            }
        )
    )
    snapshot = asyncio.run(
        EnphaseBatteryAdapter(
            hass, "sensor.soc", "sensor.capacity", "sensor.charge", "sensor.reserve"
        ).async_snapshot()
    )
    assert snapshot is not None
    assert snapshot.state_of_charge == pytest.approx(0.82)
    assert snapshot.usable_capacity_kwh == pytest.approx(10.24)
    assert snapshot.charging_power_kw == pytest.approx(2.5)
    assert snapshot.reserve_percent == 20
    assert snapshot.captured_at == captured


@pytest.mark.parametrize("missing", ["sensor.soc", "sensor.capacity"])
def test_enphase_adapter_returns_none_for_missing_required_entity(missing) -> None:
    values = {
        "sensor.soc": state("82", "%"),
        "sensor.capacity": state("10240", "Wh"),
    }
    values.pop(missing)
    hass = SimpleNamespace(states=States(values))
    result = asyncio.run(
        EnphaseBatteryAdapter(hass, "sensor.soc", "sensor.capacity").async_snapshot()
    )
    assert result is None


def test_enphase_adapter_rejects_malformed_values() -> None:
    hass = SimpleNamespace(
        states=States(
            {
                "sensor.soc": state("unknown", "%"),
                "sensor.capacity": state("10240", "Wh"),
            }
        )
    )
    assert (
        asyncio.run(
            EnphaseBatteryAdapter(
                hass, "sensor.soc", "sensor.capacity"
            ).async_snapshot()
        )
        is None
    )


def test_forecast_solar_converts_response_and_preserves_timezone_intervals() -> None:
    response = {
        "wh_period": {
            "2026-10-25T01:00:00+02:00": 500,
            "2026-10-25T02:00:00+02:00": 1250,
            "2026-10-25T03:00:00+01:00": 750,
        },
        "watts": {},
    }
    service = Service(response)
    forecast = asyncio.run(
        ForecastSolarAdapter(
            SimpleNamespace(services=service), "entry-1"
        ).async_forecast()
    )
    assert forecast is not None
    assert len(forecast.points) == 3
    assert forecast.points[0].start_time.isoformat() == "2026-10-25T01:00:00+02:00"
    assert forecast.points[0].end_time.isoformat() == "2026-10-25T02:00:00+02:00"
    assert forecast.points[1].end_time.isoformat() == "2026-10-25T03:00:00+01:00"
    assert forecast.points[2].energy_kwh == pytest.approx(0.75)


@pytest.mark.parametrize("response", [None, {}, {"wh_period": {}}, {"wh_period": []}])
def test_forecast_solar_returns_none_for_empty_or_malformed_response(response) -> None:
    service = Service(response)
    result = asyncio.run(
        ForecastSolarAdapter(
            SimpleNamespace(services=service), "entry-1"
        ).async_forecast()
    )
    assert result is None
