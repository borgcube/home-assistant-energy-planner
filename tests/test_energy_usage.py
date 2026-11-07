"""Tests for energy-meter usage estimation."""

from datetime import UTC, datetime, timedelta

import pytest
from energy_planner.energy_usage import estimate_usage_from_statistics


def test_estimate_usage_uses_active_energy_changes() -> None:
    start = datetime(2026, 11, 1, tzinfo=UTC)
    rows = [
        {"start": start + timedelta(hours=index), "sum": total}
        for index, total in enumerate((10.0, 10.8, 11.6, 11.6, 12.8))
    ]

    estimate = estimate_usage_from_statistics(rows, unit="kWh")

    assert estimate is not None
    assert estimate.average_power_kw == pytest.approx(0.8)
    assert estimate.active_hours == pytest.approx(3.0)
    assert estimate.utilization_percent == pytest.approx(75.0)
    assert estimate.samples == 3


def test_estimate_usage_normalizes_wh_and_ignores_meter_reset() -> None:
    start = datetime(2026, 11, 1, tzinfo=UTC)
    rows = [
        {"start": start, "sum": 1000},
        {"start": start + timedelta(hours=1), "sum": 1800},
        {"start": start + timedelta(hours=2), "sum": 100},
        {"start": start + timedelta(hours=3), "sum": 900},
    ]

    estimate = estimate_usage_from_statistics(rows, unit="Wh")

    assert estimate is not None
    assert estimate.average_power_kw == pytest.approx(0.8)
    assert estimate.samples == 2


def test_estimate_usage_returns_none_without_active_changes() -> None:
    start = datetime(2026, 11, 1, tzinfo=UTC)
    rows = [
        {"start": start + timedelta(hours=index), "sum": 2.0}
        for index in range(3)
    ]

    assert estimate_usage_from_statistics(rows, unit="kWh") is None
