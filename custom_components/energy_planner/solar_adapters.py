"""Forecast.Solar provider adapter for Home Assistant service responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import SolarForecast, SolarForecastPoint


@dataclass(frozen=True, slots=True)
class ForecastSolarAdapter:
    """Call Forecast.Solar and normalize its period response."""

    hass: Any
    config_entry: str
    start: datetime | None = None
    end: datetime | None = None
    resolution: str = "raw"
    key: str = "forecast_solar"

    async def async_forecast(self) -> SolarForecast | None:
        """Return the current forecast, or ``None`` if the response is unusable."""
        data: dict[str, Any] = {"config_entry": self.config_entry}
        if self.start is not None:
            data["start"] = self.start
        if self.end is not None:
            data["end"] = self.end
        if self.resolution:
            data["resolution"] = self.resolution
        response = await self.hass.services.async_call(
            "forecast_solar",
            "get_forecast",
            data,
            blocking=True,
            return_response=True,
        )
        return self._parse_response(response)

    def _parse_response(self, response: Any) -> SolarForecast | None:
        payload = _response_mapping(response)
        if payload is None:
            return None
        energy = payload.get("wh_period")
        if not isinstance(energy, Mapping) or not energy:
            return None

        rows: list[tuple[datetime, float]] = []
        for raw_start, raw_wh in energy.items():
            start = _parse_datetime(raw_start)
            try:
                wh = float(raw_wh)
            except (TypeError, ValueError):
                return None
            if start is None or wh < 0 or wh != wh:
                return None
            rows.append((start, wh))
        rows.sort(key=lambda row: row[0])
        if not rows or len({start for start, _ in rows}) != len(rows):
            return None

        default_delta = _resolution_delta(self.resolution)
        points = []
        for index, (start, wh) in enumerate(rows):
            if index + 1 < len(rows):
                finish = rows[index + 1][0]
            elif index:
                finish = start + (start - rows[index - 1][0])
            else:
                finish = start + default_delta
            if finish <= start:
                return None
            points.append(
                SolarForecastPoint(
                    start_time=start,
                    end_time=finish,
                    energy_kwh=wh / 1000,
                )
            )
        return SolarForecast(generated_at=datetime.now(UTC), points=tuple(points))


def _response_mapping(response: Any) -> Mapping[str, Any] | None:
    if isinstance(response, Mapping):
        return response.get("response", response)
    as_dict = getattr(response, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
        return value if isinstance(value, Mapping) else None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _resolution_delta(resolution: str) -> timedelta:
    return timedelta(hours=1) if resolution == "hourly" else timedelta(hours=1)
