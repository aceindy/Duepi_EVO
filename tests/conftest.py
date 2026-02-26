"""Test stubs for Home Assistant modules used by unit tests."""

from __future__ import annotations

import enum
from pathlib import Path
import sys
import types


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    ha_mod = types.ModuleType("homeassistant")
    ha_components_mod = types.ModuleType("homeassistant.components")
    ha_climate_mod = types.ModuleType("homeassistant.components.climate")
    ha_const_mod = types.ModuleType("homeassistant.const")

    class HVACMode(str, enum.Enum):
        OFF = "off"
        HEAT = "heat"

    class Platform(str, enum.Enum):
        CLIMATE = "climate"
        SENSOR = "sensor"

    ha_climate_mod.HVACMode = HVACMode
    ha_const_mod.Platform = Platform

    sys.modules["homeassistant"] = ha_mod
    sys.modules["homeassistant.components"] = ha_components_mod
    sys.modules["homeassistant.components.climate"] = ha_climate_mod
    sys.modules["homeassistant.const"] = ha_const_mod


_install_homeassistant_stubs()


def _install_duepi_namespace_stub() -> None:
    """Prevent importing integration __init__.py during unit tests."""
    if "custom_components.duepi_evo" in sys.modules:
        return

    repo_root = Path(__file__).resolve().parents[1]
    custom_components_dir = repo_root / "custom_components"
    duepi_dir = custom_components_dir / "duepi_evo"

    custom_components_pkg = types.ModuleType("custom_components")
    custom_components_pkg.__path__ = [str(custom_components_dir)]
    sys.modules.setdefault("custom_components", custom_components_pkg)

    duepi_pkg = types.ModuleType("custom_components.duepi_evo")
    duepi_pkg.__path__ = [str(duepi_dir)]
    sys.modules["custom_components.duepi_evo"] = duepi_pkg


_install_duepi_namespace_stub()
