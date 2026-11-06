"""Provider adapters for hourly electricity-price entities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .contracts import PriceProviderAdapter
from .pricing import PriceTimeline, parse_price_points


@dataclass(frozen=True, slots=True)
class GenericHourlyPriceAdapter:
    """Adapt common Home Assistant hourly-price attribute conventions.

    It supports ``data``, ``hourly_prices``, and ``prices`` while provider
    adapters for a known integration can be introduced later with more precise
    validation and metadata.
    """

    key: str = "generic_hourly_price"

    def supports(self, attributes: dict[str, Any]) -> bool:
        """Return whether a known hourly list is present."""
        return any(isinstance(attributes.get(key), list) for key in _DATA_KEYS)

    def normalize(self, attributes: dict[str, Any]) -> PriceTimeline:
        """Return provider-neutral spot-price points."""
        raw_data, source_format = self._find_hourly_data(attributes)
        return PriceTimeline(
            points=tuple(parse_price_points(raw_data)), source_format=source_format
        )

    @staticmethod
    def _find_hourly_data(
        attributes: dict[str, Any],
    ) -> tuple[Iterable[dict[str, Any]], str]:
        for key in _DATA_KEYS:
            value = attributes.get(key)
            if isinstance(value, list) and all(
                isinstance(item, dict) for item in value
            ):
                return value, key
        raise ValueError(
            "The configured price sensor needs a data, hourly_prices, "
            "or prices attribute"
        )


class PriceAdapterRegistry:
    """Select a price adapter without coupling planner code to a provider."""

    def __init__(self, adapters: tuple[PriceProviderAdapter, ...]) -> None:
        """Initialize the ordered adapter registry."""
        self._adapters = adapters

    def select(self, attributes: dict[str, Any]) -> PriceProviderAdapter:
        """Return the first adapter supporting these source attributes."""
        for adapter in self._adapters:
            if adapter.supports(attributes):
                return adapter
        raise ValueError("No installed price adapter supports this sensor")


_DATA_KEYS = ("data", "hourly_prices", "prices")
DEFAULT_PRICE_ADAPTERS = PriceAdapterRegistry((GenericHourlyPriceAdapter(),))
