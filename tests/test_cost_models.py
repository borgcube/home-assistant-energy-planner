"""Focused tests for configurable electricity cost models."""

from datetime import datetime, time

import pytest
from energy_planner.cost_models import (
    FlatRateCostModel,
    TimeOfUseCostModel,
    build_cost_model,
)


def test_time_of_use_boundaries_are_start_inclusive_and_end_exclusive() -> None:
    """Peak pricing applies exactly at its start, but not at its end."""
    model = TimeOfUseCostModel(
        peak_markup=0.12,
        off_peak_markup=0.03,
        monthly_fixed_cost=18.0,
        peak_start=time(7),
        peak_end=time(23),
    )

    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-06T06:59+01:00")
    ) == pytest.approx(0.23)
    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-06T07:00+01:00")
    ) == pytest.approx(0.32)
    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-06T23:00+01:00")
    ) == pytest.approx(0.23)
    assert model.fixed_monthly_cost() == 18.0


def test_time_of_use_supports_overnight_peak_schedule() -> None:
    """An interval crossing midnight remains peak on both sides of midnight."""
    model = TimeOfUseCostModel(0.10, 0.02, 0.0, time(22), time(7))

    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-06T22:00+01:00")
    ) == pytest.approx(0.30)
    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-07T06:59+01:00")
    ) == pytest.approx(0.30)
    assert model.import_price(
        0.20, datetime.fromisoformat("2026-11-07T07:00+01:00")
    ) == pytest.approx(0.22)


def test_export_price_applies_compensation_without_touching_fixed_cost() -> None:
    """Export credit is separate from import markup and monthly charges."""
    model = build_cost_model(
        {
            "tariff": "time_of_use",
            "peak_markup": 0.10,
            "off_peak_markup": 0.02,
            "monthly_fixed_cost": 25.0,
            "export_compensation": 0.04,
        }
    )

    assert isinstance(model, TimeOfUseCostModel)
    assert model.export_price(
        0.20, datetime.fromisoformat("2026-11-06T12:00+01:00")
    ) == pytest.approx(0.24)
    assert model.fixed_monthly_cost() == 25.0


def test_builder_preserves_backward_compatible_flat_defaults() -> None:
    """An empty builder configuration produces the original neutral flat model."""
    model = build_cost_model()

    assert model == FlatRateCostModel(0.0, 0.0, 0.0)
    assert model.import_price(
        0.21, datetime.fromisoformat("2026-11-06T12:00+01:00")
    ) == pytest.approx(0.21)
