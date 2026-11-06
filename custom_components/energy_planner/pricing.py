"""Pure price normalization utilities used by the Energy Planner coordinator."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One normalized hourly market price."""

    start_time: datetime
    end_time: datetime
    spot_price_per_kwh: float
    price_per_kwh: float

    def as_dict(self) -> dict[str, Any]:
        """Return the Home Assistant-card compatible representation."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "spot_price_per_kwh": self.spot_price_per_kwh,
            "price_per_kwh": self.price_per_kwh,
        }


@dataclass(frozen=True, slots=True)
class PriceTimeline:
    """Normalized electricity prices and their source-data quality."""

    points: tuple[PricePoint, ...]
    source_format: str

    @property
    def resolution_minutes(self) -> int | float | None:
        """Return the smallest normalized slot width in minutes."""
        if not self.points:
            return None
        durations = [
            (point.end_time - point.start_time).total_seconds() / 60
            for point in self.points
            if point.end_time > point.start_time
        ]
        if not durations:
            return None
        resolution = min(durations)
        return int(resolution) if resolution.is_integer() else resolution

    @property
    def current(self) -> PricePoint | None:
        """Return the point containing the current local time when present."""
        now = datetime.now().astimezone()
        return next(
            (
                point
                for point in self.points
                if point.start_time <= now < point.end_time
            ),
            None,
        )


def parse_price_points(raw_data: Iterable[dict[str, Any]]) -> list[PricePoint]:
    """Parse common time-series price records without applying a cost model."""
    parsed: list[tuple[datetime, float]] = []
    for item in raw_data:
        start = _parse_datetime(_required(item, "start_time", "start", "datetime"))
        price = float(_required(item, "price_per_kwh", "price", "value"))
        parsed.append((start, price))

    if not parsed:
        raise ValueError("The configured price sensor has no hourly prices")

    parsed.sort(key=lambda point: point[0])
    positive_gaps = [
        (current_start - previous_start).total_seconds()
        for (previous_start, _), (current_start, _) in zip(parsed, parsed[1:])
        if current_start > previous_start
    ]
    final_slot_duration = timedelta(
        seconds=min(positive_gaps) if positive_gaps else 60 * 60
    )
    return [
        PricePoint(
            start_time=start,
            end_time=(
                parsed[index + 1][0]
                if index + 1 < len(parsed)
                else start + final_slot_duration
            ),
            spot_price_per_kwh=spot_price,
            price_per_kwh=spot_price,
        )
        for index, (start, spot_price) in enumerate(parsed)
    ]


def _required(item: dict[str, Any], *keys: str) -> Any:
    """Return the first present non-null key from a price item."""
    for key in keys:
        if item.get(key) is not None:
            return item[key]
    raise ValueError(f"A price item is missing one of: {', '.join(keys)}")


def _parse_datetime(value: Any) -> datetime:
    """Parse an ISO 8601 timestamp and require timezone-aware input."""
    if not isinstance(value, str):
        raise ValueError("A price timestamp must be an ISO 8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("A price timestamp must include its timezone")
    return parsed
