"""Constants for the Duepi EVO integration."""

from __future__ import annotations

from homeassistant.components.climate import HVACMode
from homeassistant.const import Platform

DOMAIN = "duepi_evo"
PLATFORMS: list[Platform] = [Platform.CLIMATE]

DEFAULT_NAME = "Duepi EVO"
DEFAULT_HOST = ""
DEFAULT_PORT = 23
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MIN_TEMP = 16.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_NOFEEDBACK = 16.0
DEFAULT_AUTO_RESET = False
DEFAULT_UNIQUE_ID = "duepi_unique"
DEFAULT_INIT_COMMAND = False

CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_AUTO_RESET = "auto_reset"
CONF_NOFEEDBACK = "temp_nofeedback"
CONF_UNIQUE_ID = "unique_id"
CONF_INIT_COMMAND = "init_command"

STATE_ACK = 0x00000020
STATE_OFF = 0x00000020
STATE_START = 0x01000000
STATE_ON = 0x02000000
STATE_CLEAN = 0x04000000
STATE_COOL = 0x08000000
STATE_ECO = 0x10000000

GET_SETPOINT = "C6000"
GET_FLUGASTEMP = "D0000"
GET_TEMPERATURE = "D1000"
GET_POWERLEVEL = "D3000"
GET_PELLETSPEED = "D4000"
REMOTE_RESET = "D6000"
GET_STATUS = "D9000"
GET_ERRORSTATE = "DA000"
GET_EXHFANSPEED = "EF000"
GET_INITCOMMAND = "DC000"

SET_POWERLEVEL = "F00x0"
SET_TEMPERATURE = "F2xx0"

SUPPORT_MODES = [HVACMode.HEAT, HVACMode.OFF]
FAN_MODES = ["Off", "Min", "Low", "Medium", "High", "Max"]
FAN_MODE_MAP = {"Off": 0, "Min": 1, "Low": 2, "Medium": 3, "High": 4, "Max": 5}
FAN_MODE_MAP_REV = {value: key for key, value in FAN_MODE_MAP.items()}
AUTO_RESET_ERRORS = {"Out of pellets", "Ignition failure"}

ATTR_BURNER_STATUS = "burner_status"
ATTR_ERROR_CODE = "error_code"
ATTR_EXH_FAN_SPEED = "exh_fan_speed"
ATTR_FLU_GAS_TEMP = "flu_gas_temp"
ATTR_PELLET_SPEED = "pellet_speed"
ATTR_POWER_LEVEL = "power_level"


def entry_unique_id(host: str, port: int) -> str:
    """Build a stable config-entry unique ID from host/port."""
    return f"{host}:{port}"


def climate_unique_id_from_entry_unique_id(config_entry_unique_id: str) -> str:
    """Build a stable climate entity unique ID from the config-entry unique ID."""
    return f"{config_entry_unique_id}:climate"


def climate_unique_id(host: str, port: int) -> str:
    """Build a stable climate entity unique ID from host/port."""
    return climate_unique_id_from_entry_unique_id(entry_unique_id(host, port))
