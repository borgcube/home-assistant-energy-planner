"""Provider-independent, price-only appliance scheduling primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .pricing import PricePoint, PriceTimeline


@dataclass(frozen=True, slots=True)
class AppliancePlanRequest:
    """The constraints for placing one appliance run into a price timeline."""

    appliance_id: str
    duration: timedelta
    deadline: datetime
    average_power_kw: float
    earliest_start: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScheduledWindow:
    """A least-cost contiguous execution window for an appliance plan."""

    appliance_id: str
    start_time: datetime
    end_time: datetime
    estimated_cost: float
    average_price_per_kwh: float


def find_lowest_cost_window(
    timeline: PriceTimeline, request: AppliancePlanRequest
) -> ScheduledWindow | None:
    """Return the least-cost contiguous timeline window that meets constraints.

    This makes no device calls. It is safe for plan-only and notification
    modes, and becomes the common optimiser input for verified controllers.
    """
    if request.duration <= timedelta():
        raise ValueError("Appliance duration must be greater than zero")
    if request.average_power_kw <= 0:
        raise ValueError("Appliance average power must be greater than zero")
    if not timeline.points:
        return None

    earliest_start = request.earliest_start or timeline.points[0].start_time
    eligible = [
        point
        for point in timeline.points
        if point.start_time >= earliest_start and point.end_time <= request.deadline
    ]
    candidates = _contiguous_windows(eligible, request.duration)
    if not candidates:
        return None

    start, end, points = min(
        candidates,
        key=lambda candidate: _estimated_cost(candidate[2], request.average_power_kw),
    )
    estimated_cost = _estimated_cost(points, request.average_power_kw)
    energy_kwh = request.average_power_kw * (request.duration.total_seconds() / 3600)
    return ScheduledWindow(
        appliance_id=request.appliance_id,
        start_time=start,
        end_time=end,
        estimated_cost=estimated_cost,
        average_price_per_kwh=estimated_cost / energy_kwh,
    )


def _contiguous_windows(
    points: list[PricePoint], duration: timedelta
) -> list[tuple[datetime, datetime, tuple[PricePoint, ...]]]:
    """Return windows whose source slots exactly cover the requested duration."""
    windows: list[tuple[datetime, datetime, tuple[PricePoint, ...]]] = []
    for start_index, start_point in enumerate(points):
        selected: list[PricePoint] = []
        elapsed = timedelta()
        previous: PricePoint | None = None
        for point in points[start_index:]:
            if previous and previous.end_time != point.start_time:
                break
            selected.append(point)
            elapsed += point.end_time - point.start_time
            if elapsed == duration:
                windows.append(
                    (start_point.start_time, point.end_time, tuple(selected))
                )
                break
            if elapsed > duration:
                break
            previous = point
    return windows


def _estimated_cost(points: tuple[PricePoint, ...], power_kw: float) -> float:
    """Calculate cost for a fixed-power appliance across execution slots."""
    return sum(
        point.price_per_kwh
        * power_kw
        * ((point.end_time - point.start_time).total_seconds() / 3600)
        for point in points
    )
