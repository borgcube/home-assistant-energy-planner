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
        if point.start_time >= earliest_start and point.start_time < request.deadline
    ]
    candidates = _contiguous_windows(eligible, request.duration, request.deadline)
    if not candidates:
        return None

    start, end, points = min(
        candidates,
        key=lambda candidate: _estimated_cost(
            candidate[2], request.average_power_kw, candidate[0], candidate[1]
        ),
    )
    estimated_cost = _estimated_cost(
        points, request.average_power_kw, start, end
    )
    energy_kwh = request.average_power_kw * (request.duration.total_seconds() / 3600)
    return ScheduledWindow(
        appliance_id=request.appliance_id,
        start_time=start,
        end_time=end,
        estimated_cost=estimated_cost,
        average_price_per_kwh=estimated_cost / energy_kwh,
    )


def find_lowest_price_window(
    timeline: PriceTimeline,
    *,
    duration: timedelta,
    earliest_start: datetime,
    deadline: datetime,
) -> ScheduledWindow | None:
    """Return the cheapest future window without assuming an appliance.

    A one-kilowatt virtual load makes the returned cost equal to the energy
    price for the requested duration. This keeps the recommendation useful
    for automations while leaving appliance power and control out of scope.
    """
    return find_lowest_cost_window(
        timeline,
        AppliancePlanRequest(
            appliance_id="price_window",
            duration=duration,
            deadline=deadline,
            average_power_kw=1.0,
            earliest_start=earliest_start,
        ),
    )


def _contiguous_windows(
    points: list[PricePoint], duration: timedelta, deadline: datetime
) -> list[tuple[datetime, datetime, tuple[PricePoint, ...]]]:
    """Return windows that cover the requested duration without a price gap."""
    windows: list[tuple[datetime, datetime, tuple[PricePoint, ...]]] = []
    for start_index, start_point in enumerate(points):
        selected: list[PricePoint] = []
        candidate_end = start_point.start_time + duration
        previous_end: datetime | None = None
        for point in points[start_index:]:
            if previous_end and previous_end != point.start_time:
                break
            selected.append(point)
            previous_end = point.end_time
            if candidate_end <= point.end_time:
                if candidate_end <= deadline:
                    windows.append(
                        (start_point.start_time, candidate_end, tuple(selected))
                    )
                break
    return windows


def _estimated_cost(
    points: tuple[PricePoint, ...],
    power_kw: float,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate cost for a fixed-power appliance over a possibly partial window."""
    return sum(
        point.price_per_kwh
        * power_kw
        * (
            (
                min(point.end_time, window_end)
                - max(point.start_time, window_start)
            ).total_seconds()
            / 3600
        )
        for point in points
    )
