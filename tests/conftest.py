"""Test stubs for Home Assistant modules used by unit tests."""

from __future__ import annotations

import enum
from pathlib import Path
import sys
import types
from typing import Any


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    ha_mod = types.ModuleType("homeassistant")
    ha_components_mod = types.ModuleType("homeassistant.components")
    ha_binary_sensor_mod = types.ModuleType("homeassistant.components.binary_sensor")
    ha_climate_mod = types.ModuleType("homeassistant.components.climate")
    ha_sensor_mod = types.ModuleType("homeassistant.components.sensor")
    ha_const_mod = types.ModuleType("homeassistant.const")
    ha_config_entries_mod = types.ModuleType("homeassistant.config_entries")
    ha_core_mod = types.ModuleType("homeassistant.core")
    ha_helpers_mod = types.ModuleType("homeassistant.helpers")
    ha_entity_platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_update_coordinator_mod = types.ModuleType("homeassistant.helpers.update_coordinator")

    class HVACMode(str, enum.Enum):
        OFF = "off"
        HEAT = "heat"

    class Platform(str, enum.Enum):
        CLIMATE = "climate"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    class UnitOfTemperature(str, enum.Enum):
        CELSIUS = "degC"

    class BinarySensorEntity:
        """Minimal binary sensor entity stub."""

    class SensorEntity:
        """Minimal sensor entity stub."""

    class _DescriptionBase:
        """Populate attributes passed by entity descriptions."""

        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    class BinarySensorEntityDescription(_DescriptionBase):
        """Minimal binary sensor entity description stub."""

    class SensorEntityDescription(_DescriptionBase):
        """Minimal sensor entity description stub."""

    class SensorDeviceClass(str, enum.Enum):
        TEMPERATURE = "temperature"

    class ConfigEntry:
        """Minimal config entry stub."""

    class HomeAssistant:
        """Minimal Home Assistant stub."""

    class CoordinatorEntity:
        """Minimal coordinator entity stub."""

        def __init__(self, coordinator: Any) -> None:
            self.coordinator = coordinator

        def __class_getitem__(cls, _item: Any):
            return cls

    class DataUpdateCoordinator:
        """Minimal data update coordinator stub."""

        def __class_getitem__(cls, _item: Any):
            return cls

    class UpdateFailed(Exception):
        """Minimal update failure stub."""

    ha_climate_mod.HVACMode = HVACMode
    ha_binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    ha_binary_sensor_mod.BinarySensorEntityDescription = BinarySensorEntityDescription
    ha_sensor_mod.SensorDeviceClass = SensorDeviceClass
    ha_sensor_mod.SensorEntity = SensorEntity
    ha_sensor_mod.SensorEntityDescription = SensorEntityDescription
    ha_const_mod.Platform = Platform
    ha_const_mod.CONF_HOST = "host"
    ha_const_mod.CONF_NAME = "name"
    ha_const_mod.CONF_PORT = "port"
    ha_const_mod.UnitOfTemperature = UnitOfTemperature
    ha_config_entries_mod.ConfigEntry = ConfigEntry
    ha_core_mod.HomeAssistant = HomeAssistant
    ha_entity_platform_mod.AddEntitiesCallback = Any
    ha_update_coordinator_mod.CoordinatorEntity = CoordinatorEntity
    ha_update_coordinator_mod.DataUpdateCoordinator = DataUpdateCoordinator
    ha_update_coordinator_mod.UpdateFailed = UpdateFailed

    sys.modules["homeassistant"] = ha_mod
    sys.modules["homeassistant.components"] = ha_components_mod
    sys.modules["homeassistant.components.binary_sensor"] = ha_binary_sensor_mod
    sys.modules["homeassistant.components.climate"] = ha_climate_mod
    sys.modules["homeassistant.components.sensor"] = ha_sensor_mod
    sys.modules["homeassistant.const"] = ha_const_mod
    sys.modules["homeassistant.config_entries"] = ha_config_entries_mod
    sys.modules["homeassistant.core"] = ha_core_mod
    sys.modules["homeassistant.helpers"] = ha_helpers_mod
    sys.modules["homeassistant.helpers.entity_platform"] = ha_entity_platform_mod
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_update_coordinator_mod


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
