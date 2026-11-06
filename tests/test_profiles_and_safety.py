import pytest
from energy_planner.profiles import ApplianceProfile, profile_map_from_storage


def test_profile_round_trip_keeps_execution_and_monitoring_settings() -> None:
    profile = ApplianceProfile(
        profile_id="dishwasher",
        name="Dishwasher",
        duration_minutes=90,
        average_power_kw=1.2,
        execution_mode="notify_at_start",
        power_entity="sensor.dishwasher_power",
        power_threshold_w=75,
        load_group="kitchen",
    )

    loaded = profile_map_from_storage({"dishwasher": profile.as_dict()})["dishwasher"]

    assert loaded.as_dict() == profile.as_dict()


def test_profile_loader_ignores_malformed_records() -> None:
    profiles = profile_map_from_storage(
        {
            "good": {
                "name": "Good",
                "duration_minutes": 60,
                "average_power_kw": 1,
            },
            "bad": {"name": "Missing runtime"},
            "not-a-profile": "invalid",
        }
    )

    assert list(profiles) == ["good"]


def test_automatic_profile_requires_verified_delayed_start_and_power_monitor() -> None:
    pytest.importorskip("homeassistant")
    from energy_planner.coordinator import validate_automatic_profile

    profile = ApplianceProfile(
        profile_id="washer",
        name="Washer",
        duration_minutes=60,
        average_power_kw=0.8,
        execution_mode="automatic",
        start_entity="select.washer_program",
        start_service="select.select_option",
    )

    assert "verified" in (validate_automatic_profile(profile) or "")

    profile.verified_delayed_start = True
    assert "power-monitoring" in (validate_automatic_profile(profile) or "")


def test_automatic_profile_blocks_generic_immediate_control() -> None:
    pytest.importorskip("homeassistant")
    from energy_planner.coordinator import validate_automatic_profile

    profile = ApplianceProfile(
        profile_id="unsafe",
        name="Unsafe",
        duration_minutes=60,
        average_power_kw=0.8,
        execution_mode="automatic",
        start_entity="switch.washer",
        start_service="switch.turn_on",
        verified_delayed_start=True,
        power_entity="sensor.washer_power",
    )

    assert "Generic immediate-control" in (validate_automatic_profile(profile) or "")
