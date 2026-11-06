"""Test setup that loads pure planner modules without Home Assistant installed."""

from __future__ import annotations

import sys
import types
from pathlib import Path

component_path = Path(__file__).parents[1] / "custom_components" / "energy_planner"
package = types.ModuleType("energy_planner")
package.__path__ = [str(component_path)]
sys.modules["energy_planner"] = package
