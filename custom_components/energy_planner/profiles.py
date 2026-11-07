"""Persistent appliance profiles and their safe execution settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .const import EXECUTION_PLAN_ONLY


@dataclass(slots=True)
class ApplianceProfile:
    """A reusable appliance plan with an explicit execution mode."""

    profile_id: str
    name: str
    duration_minutes: int
    average_power_kw: float
    execution_mode: str = EXECUTION_PLAN_ONLY
    start_entity: str | None = None
    start_service: str | None = None
    service_data: dict[str, Any] = field(default_factory=dict)
    verified_delayed_start: bool = False
    enabled: bool = True
    power_entity: str | None = None
    power_threshold_w: float = 50.0
    load_group: str | None = None
    energy_entity: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-safe profile data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplianceProfile:
        """Build a profile from persisted or service data."""
        return cls(
            profile_id=str(data["profile_id"]),
            name=str(data.get("name") or data["profile_id"]),
            duration_minutes=int(data["duration_minutes"]),
            average_power_kw=float(data["average_power_kw"]),
            energy_entity=data.get("energy_entity"),
            execution_mode=str(data.get("execution_mode", EXECUTION_PLAN_ONLY)),
            start_entity=data.get("start_entity"),
            start_service=data.get("start_service"),
            service_data=dict(data.get("service_data") or {}),
            verified_delayed_start=bool(data.get("verified_delayed_start", False)),
            enabled=bool(data.get("enabled", True)),
            power_entity=data.get("power_entity"),
            power_threshold_w=float(data.get("power_threshold_w", 50.0)),
            load_group=data.get("load_group"),
        )


def profile_map_from_storage(value: Any) -> dict[str, ApplianceProfile]:
    """Load a tolerant profile map, ignoring malformed individual records."""
    if not isinstance(value, dict):
        return {}
    profiles: dict[str, ApplianceProfile] = {}
    for profile_id, raw in value.items():
        if not isinstance(raw, dict):
            continue
        try:
            data = {"profile_id": profile_id, **raw}
            profile = ApplianceProfile.from_dict(data)
        except (KeyError, TypeError, ValueError):
            continue
        profiles[profile.profile_id] = profile
    return profiles
