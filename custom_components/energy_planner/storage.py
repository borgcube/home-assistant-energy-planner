"""Persistent state for Energy Planner recommendations and profiles."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, MAX_PLAN_HISTORY, STORAGE_VERSION
from .profiles import ApplianceProfile, profile_map_from_storage


class PlannerStorage:
    """Small versioned store scoped to one Energy Planner config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the entry-scoped store."""
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            atomic_writes=True,
        )

    async def async_load(self) -> dict[str, Any]:
        """Load and normalize persisted state."""
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return {"last_plan": None, "plan_history": [], "profiles": {}}
        history = data.get("plan_history")
        normalized_history = (
            [dict(plan) for plan in history if isinstance(plan, dict)]
            if isinstance(history, list)
            else []
        )
        return {
            "last_plan": (
                dict(data["last_plan"])
                if isinstance(data.get("last_plan"), dict)
                else None
            ),
            "plan_history": normalized_history[:MAX_PLAN_HISTORY],
            "profiles": profile_map_from_storage(data.get("profiles")),
        }

    async def async_save(
        self,
        *,
        last_plan: dict[str, Any] | None,
        plan_history: list[dict[str, Any]],
        profiles: dict[str, ApplianceProfile],
    ) -> None:
        """Persist the current JSON-safe state."""
        await self._store.async_save(
            {
                "last_plan": dict(last_plan) if last_plan else None,
                "plan_history": [
                    dict(plan) for plan in plan_history[:MAX_PLAN_HISTORY]
                ],
                "profiles": {
                    profile_id: profile.as_dict()
                    for profile_id, profile in profiles.items()
                },
            }
        )
