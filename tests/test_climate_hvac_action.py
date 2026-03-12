"""Unit tests for climate hvac_action mapping."""

from __future__ import annotations

import enum
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from homeassistant.components.climate import HVACMode


def _install_climate_import_stubs() -> None:
    """Install the minimal Home Assistant stubs needed for climate.py."""
    ha_climate_mod = sys.modules["homeassistant.components.climate"]

    class HVACAction(str, enum.Enum):
        OFF = "off"
        HEATING = "heating"
        IDLE = "idle"

    class ClimateEntity:
        """Minimal climate entity stub."""

    class ClimateEntityFeature(enum.IntFlag):
        TARGET_TEMPERATURE = 1
        FAN_MODE = 2
        TURN_OFF = 4
        TURN_ON = 8

    class UnitOfTemperature(str, enum.Enum):
        CELSIUS = "°C"

    class DummySchema:
        def extend(self, *_args, **_kwargs):
            return self

    ha_climate_mod.HVACAction = HVACAction
    ha_climate_mod.ClimateEntity = ClimateEntity
    ha_climate_mod.ClimateEntityFeature = ClimateEntityFeature
    ha_climate_mod.UnitOfTemperature = UnitOfTemperature
    ha_climate_mod.PLATFORM_SCHEMA = DummySchema()

    ha_const_mod = sys.modules["homeassistant.const"]
    ha_const_mod.ATTR_TEMPERATURE = "temperature"
    ha_const_mod.CONF_HOST = "host"
    ha_const_mod.CONF_NAME = "name"
    ha_const_mod.CONF_PORT = "port"
    ha_const_mod.CONF_SCAN_INTERVAL = "scan_interval"
    ha_const_mod.REVOLUTIONS_PER_MINUTE = "rpm"

    helpers_mod = types.ModuleType("homeassistant.helpers")
    helpers_mod.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers_mod

    cv_mod = types.ModuleType("homeassistant.helpers.config_validation")
    cv_mod.string = str
    cv_mod.positive_int = int
    cv_mod.positive_float = float
    cv_mod.boolean = bool
    sys.modules["homeassistant.helpers.config_validation"] = cv_mod

    entity_platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_mod.AddEntitiesCallback = object
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_mod

    typing_mod = types.ModuleType("homeassistant.helpers.typing")
    typing_mod.ConfigType = dict
    typing_mod.DiscoveryInfoType = dict
    sys.modules["homeassistant.helpers.typing"] = typing_mod

    update_coordinator_mod = types.ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    update_coordinator_mod.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator_mod

    config_entries_mod = types.ModuleType("homeassistant.config_entries")
    config_entries_mod.SOURCE_IMPORT = "import"
    config_entries_mod.ConfigEntry = object
    sys.modules["homeassistant.config_entries"] = config_entries_mod

    core_mod = types.ModuleType("homeassistant.core")
    core_mod.HomeAssistant = object
    sys.modules["homeassistant.core"] = core_mod

    util_mod = types.ModuleType("homeassistant.util")
    util_mod.slugify = lambda value: str(value).lower().replace(" ", "_")
    sys.modules["homeassistant.util"] = util_mod

    repo_root = Path(__file__).resolve().parents[1]
    duepi_dir = repo_root / "custom_components" / "duepi_evo"
    coordinator_mod = types.ModuleType("custom_components.duepi_evo.coordinator")
    coordinator_mod.DuepiEvoCoordinator = object
    coordinator_mod.__file__ = str(duepi_dir / "coordinator.py")
    sys.modules["custom_components.duepi_evo.coordinator"] = coordinator_mod


def test_hvac_action_is_idle_while_cooling_down() -> None:
    """Cooling down should report idle action while staying in heat mode."""
    _install_climate_import_stubs()
    climate_module = importlib.import_module("custom_components.duepi_evo.climate")

    entity = climate_module.DuepiEvoClimateEntity.__new__(climate_module.DuepiEvoClimateEntity)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            burner_status="Cooling down",
            heating=False,
            hvac_mode=HVACMode.HEAT,
        )
    )

    assert entity.hvac_action == climate_module.HVACAction.IDLE
