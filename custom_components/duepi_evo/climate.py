"""Climate support for Duepi-evo base pellet stoves.

configuration.yaml

# Example configuration.yaml entry
climate:
  - platform: duepi_evo
    name: Qlima Viola 85
    host: 192.168.1.123
    port: 2000
    scan_interval: 60
    min_temp: 10
    max_temp: 30
    auto_reset: True
    unique_id: my_pellet_stove_1
    temp_nofeedback: 16
"""

import asyncio
import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    REVOLUTIONS_PER_MINUTE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

"""
Supported hvac modes:

- HVAC_MODE_HEAT: Heat to a target temperature (schedule off)
- HVAC_MODE_OFF:  The device runs in a continuous energy savings mode. If
                  configured as one of the supported hvac modes this mode
                  can be used to activate the vacation mode
"""
SUPPORT_MODES = [HVACMode.HEAT, HVACMode.OFF]

DEFAULT_NAME = "Duepi EVO"
DEFAULT_HOST = ""
DEFAULT_PORT = 23
DEFAULT_MIN_TEMP = 16.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_NOFEEDBACK = 16.0
DEFAULT_AUTO_RESET = False
DEFAULT_UNIQUE_ID = "duepi_unique"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_AUTO_RESET = "auto_reset"
CONF_NOFEEDBACK = "temp_nofeedback"
CONF_UNIQUE_ID = "unique_id"

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): cv.positive_float,
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): cv.positive_float,
        vol.Optional(CONF_AUTO_RESET, default=DEFAULT_AUTO_RESET): cv.boolean,
        vol.Optional(CONF_NOFEEDBACK, default=DEFAULT_NOFEEDBACK): cv.positive_float,
        vol.Optional(CONF_UNIQUE_ID, default=DEFAULT_UNIQUE_ID): cv.string,
    }
)

# constants
STATE_ACK =   0x00000020
STATE_OFF =   0x00000020
STATE_START = 0x01000000
STATE_ON =    0x02000000
STATE_CLEAN = 0x04000000
STATE_COOL =  0x08000000
STATE_ECO =   0x10000000

GET_SETPOINT =    "C6000"
GET_FLUGASTEMP =  "D0000"
GET_TEMPERATURE = "D1000"
GET_POWERLEVEL =  "D3000"
GET_PELLETSPEED = "D4000"
REMOTE_RESET =    "D6000"
GET_STATUS =      "D9000"
GET_ERRORSTATE =  "DA000"
GET_EXHFANSPEED = "EF000"

SET_POWERLEVEL =  "F00x0"
SET_TEMPERATURE = "F2xx0"

# Set to True for stoves that support setpoint retrieval
SUPPORT_SETPOINT = False

async def async_setup_platform(hass: HomeAssistant, config: ConfigType, add_devices: AddEntitiesCallback, discovery_info: DiscoveryInfoType | None = None,) -> None:
    """Set up the Duepi EVO."""
    session = async_get_clientsession(hass)
    add_devices([DuepiEvoDevice(session, config)], True)


class DuepiEvoDevice(ClimateEntity):
    """Representation of a DuepiEvoDevice."""

    def __init__(self, session, config) -> None:
        """Initialize the DuepiEvoDevice with session and config parameters."""
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_supported_features = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON)
        self._session = session
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._min_temp = config.get(CONF_MIN_TEMP)
        self._max_temp = config.get(CONF_MAX_TEMP)
        self._auto_reset = config.get(CONF_AUTO_RESET)
        self._no_feedback = config.get(CONF_NOFEEDBACK)
        self._unique_id = config.get(CONF_UNIQUE_ID)
        self._current_temperature = None
        self._target_temperature = None
        self._heating = False
        self._burner_status = None
        self._flugas_temp = None
        self._error_code = None
        self._exhaust_fan_speed = None
        self._hvac_mode = HVACMode.OFF
        self._fan_modes = ["Off", "Min", "Low", "Medium", "High", "Max"]
        self._fan_mode = self._fan_modes[2]
        self._current_fan_mode = None
        self._fan_mode_map = {"Off": 0, "Min": 1, "Low": 2, "Medium": 3, "High": 4, "Max": 5,}
        self._fan_mode_map_rev = {value: key for key, value in self._fan_mode_map.items()}
        self._pellet_speed = None
        self._error_code_map = {
            0: "All OK",
            1: "Ignition failure",
            2: "Defective suction",
            3: "Insufficient air intake",
            4: "Water temperature",
            5: "Out of pellets",
            6: "Defective pressure switch",
            7: "Unknown",
            8: "No current",
            9: "Exhaust motor failure",
            10: "Card surge",
            11: "Date expired",
            12: "Unknown",
            13: "Suction regulating sensor error",
            14: "Overheating",
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Polling needed for thermostat."""
        return True

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def target_temperature_step(self) -> float:
        """Indicate the target temperature step for this climate device."""
        return 1.0

    @property
    def temperature_unit(self) -> str:
        """Indicate the target temperature unit for this climate device."""
        return UnitOfTemperature.CELSIUS

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self._name

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach. Use environment temperature if set to None (bug)."""
        if self._target_temperature is None:
            self._target_temperature = int(self._no_feedback)
            _LOGGER.debug("%s Setpoint retrieval not supported by this stove, using temp_nofeedback %s", self._name, str(self._target_temperature),)
        return self._target_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes to entity."""
        return {
            "burner_status": self._burner_status,
            "error_code": self._error_code,
            "exh_fan_speed": f"{self._exhaust_fan_speed} {REVOLUTIONS_PER_MINUTE}",
            "flu_gas_temp": f"{self._flugas_temp} {UnitOfTemperature.CELSIUS}",
            "pellet_speed": self._pellet_speed,
            "power_level": self._fan_mode,
        }

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return SUPPORT_MODES

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        return (
            HVACAction.IDLE
            if self._burner_status in ["Eco Idle"]
            else HVACAction.HEATING
            if self._heating
            else HVACAction.OFF
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        self._fan_mode = self._current_fan_mode
        return self._fan_mode

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return self._fan_modes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        self.entity_id = f"climate.{slugify(self._name)}"
        _LOGGER.debug("Added DuepiEvoDevice with entity_id: %s", self.entity_id)

    def generate_command(self, command):
        """Format the command by adding ESC, prefix 'R', calculating checksum, and appending '&'."""
        # Prefix with 'R'
        formatted_cmd = "R" + command
        # Calculate checksum (sum of ASCII values, last 8 bits only)
        checksum = sum(ord(char) for char in formatted_cmd) & 0xFF
        # Construct final command: ESC + formatted_cmd + hex checksum + &
        return "\x1b" + formatted_cmd + f"{checksum:02X}" + "&"

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        # If fan mode is empty, return
        if fan_mode == "":
            _LOGGER.error("%s: Unable to read fan mode [%s]", self._name, fan_mode)
            return

        # Set the fan mode
        sock = None
        try:
            async with asyncio.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))
                power_level_hex_str = hex(self._fan_mode_map[fan_mode])
                data = SET_POWERLEVEL.replace("x", power_level_hex_str[2:3])
                data = self.generate_command(data)
                sock.send(data.encode())
                response = sock.recv(10).decode()
                current_state = int(response[1:9], 16)
                if not (STATE_ACK & current_state):
                    _LOGGER.error("%s: Unable to set fan mode to %s", self._name, str(fan_mode))

        except TimeoutError:
            _LOGGER.error("Time-out while setting fan mode on host: %s", self._host)

        finally:
            if sock:
                sock.close()

        self._current_fan_mode = self._fan_mode = fan_mode
      
        _LOGGER.debug("%s setting fanSpeed to %s", self.name, fan_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)

        # If target temperature is empty, return
        if target_temperature is None:
            _LOGGER.debug("%s: Unable to use target temp", self._name)
            return

        # Set the target temperature
        sock = None
        try:
            async with asyncio.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))
                set_point_int = int(target_temperature)
                set_point_hex_str = f"{set_point_int:02X}"
                data = SET_TEMPERATURE.replace("xx", set_point_hex_str)
                data = self.generate_command(data)
                sock.send(data.encode())
                response = sock.recv(10).decode()
                current_state = int(response[1:9], 16)
                if not (STATE_ACK & current_state):
                    _LOGGER.error("%s: Unable to set target temp to %s°C", self._name, str(target_temperature),)

        except TimeoutError:
            _LOGGER.error("Time-out while setting temperature on host: %s", self._host)

        finally:
            if sock:
                sock.close()

        # Update the target temperature
        self._target_temperature = target_temperature
      
        _LOGGER.debug("%s: Set target temp to %s°C", self._name, str(target_temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        sock = None
        try:
            async with asyncio.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))
                # Set the power level to 0 (Off) or 1 (Min) when changing mode
                if hvac_mode == "off":
                    self._hvac_mode = HVACMode.OFF
                    power_level_hex_str = hex(self._fan_mode_map["Off"])
                elif hvac_mode == "heat":
                    self._hvac_mode = HVACMode.HEAT
                    power_level_hex_str = hex(self._fan_mode_map["Min"])
                # Construct the command
                data = SET_POWERLEVEL.replace("x", power_level_hex_str[2:3])
                data = self.generate_command(data)
                sock.send(data.encode())
                response = sock.recv(10).decode()
                current_state = int(response[1:9], 16)
                if not (STATE_ACK & current_state):
                    _LOGGER.error("%s: unknown return value %s", self.name, response)

        except TimeoutError:
            _LOGGER.error("Time-out while setting hvac mode on host: %s", self._host)

        finally:
            if sock:
                sock.close()

        _LOGGER.debug("%s: Set hvac mode to %s", self.name, str(hvac_mode))

    async def remote_reset(self, error_code) -> None:
        """Reset and power down the stove."""
        sock = None
        try:
            async with asyncio.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))
                sock.send(self.generate_command(REMOTE_RESET).encode())
                response = sock.recv(10).decode()
                current_state = int(response[1:9], 16)
                if not (STATE_ACK & current_state):
                    _LOGGER.error("%s: unknown return value %s", self.name, response)
        except TimeoutError:
            _LOGGER.error("Time-out while resetting host: %s", self._host)
            return

        finally:
            if sock:
                sock.close()

        _LOGGER.debug("%s: %s was reset !", self.name, error_code)

    async def async_update(self) -> None:
        """Update local data with data from stove."""
        data = await self.get_data(SUPPORT_SETPOINT)
        self._burner_status = data[0]
        self._current_temperature = data[1]
        self._current_fan_mode = self._fan_mode_map_rev[data[2]]
        self._flugas_temp = data[3]
        self._exhaust_fan_speed = data[4]
        self._pellet_speed = data[5]
        self._error_code = data[6]

        # If unit support the target temperature, update it
        if SUPPORT_SETPOINT is True:
            self._target_temperature = data[7]

        # Set the hvac mode
        if self._burner_status == "Off":
            self._heating = False
            self._hvac_mode = HVACMode.OFF
        elif self._burner_status in ["Cooling down"]:
            self._heating = True
            self._hvac_mode = HVACMode.OFF
        else:
            self._heating = True
            self._hvac_mode = HVACMode.HEAT

        # When enabled, auto reset when running out of pellets or ignition failure.
        if self._auto_reset and self._error_code in ("Out of pellets", "Ignition failure",):
            await self.remote_reset(self._error_code)

    async def get_data(self, support_setpoint) -> None:
        """Get the data from the stove."""

        sock = None
        try:
            async with asyncio.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))

                # Get Burner status
                sock.send(self.generate_command(GET_STATUS).encode())
                response = sock.recv(10).decode()
                currentstate = int(response[1:9], 16)
                if STATE_START & currentstate:
                    status = "Ignition starting"
                elif STATE_ON & currentstate:
                    status = "Flame On"
                elif STATE_CLEAN & currentstate:
                    status = "Cleaning"
                elif STATE_ECO & currentstate:
                    status = "Eco idle"
                elif STATE_COOL & currentstate:
                    status = "Cooling down"
                elif STATE_OFF & currentstate:
                    status = "Off"
                else:
                    status = "Unknown state"

                # Get Fan mode (also called fan speed or power level)
                # If state is off, no need to poll, just set to 'Off'
                if status == "Off":
                    fan_mode = self._fan_mode_map["Off"]
                else:
                    sock.send(self.generate_command(GET_POWERLEVEL).encode())
                    response = sock.recv(10).decode()
                    if len(response) != 0:
                        fan_mode = int(response[1:5], 16)

                # Get Ambient temperature
                sock.send(self.generate_command(GET_TEMPERATURE).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    current_temperature = int(response[1:5], 16) / 10.0

                # Get pellet speed
                sock.send(self.generate_command(GET_PELLETSPEED).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    pellet_speed = int(response[1:5], 16)

                # Get FluGas temperature
                sock.send(self.generate_command(GET_FLUGASTEMP).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    current_flugastemp = int(response[1:5], 16)

                # Get Exhaust Fan speed
                sock.send(self.generate_command(GET_EXHFANSPEED).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    current_exhfanspeed = int(response[1:5], 16) * 10

                # Get Error code
                sock.send(self.generate_command(GET_ERRORSTATE).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    error_code_decimal = int(response[1:5], 16)
                error_code = ( self._error_code_map[error_code_decimal] if error_code_decimal < 15 else str(error_code_decimal))

                # Get & validate target temperature (Setpoint)
                sock.send(self.generate_command(GET_SETPOINT).encode())
                response = sock.recv(10).decode()
                if len(response) != 0:
                    target_temperature = int(response[1:5], 16)
                    support_setpoint = (target_temperature != 0 and self._min_temp < target_temperature < self._max_temp)

        except TimeoutError:
            _LOGGER.error("Time-out while polling host: %s", self._host)
            return None

        finally:
            if sock:
                sock.close()

        # Return the result
        result = [
            status,
            current_temperature,
            fan_mode,
            current_flugastemp,
            current_exhfanspeed,
            pellet_speed,
            error_code,
        ]
        # If unit support the target temperature, append it to the result
        if support_setpoint:
            result.append(target_temperature)

        _LOGGER.debug(
            "%s: Received burner: %s, Ambient temp: %s, Fan speed: %s, Flu gas temp: %s, Exh fan speed: %s, PelletSpeed: %s, Error code: %s, Setpoint temp: %s",
            self._name,
            status,
            str(current_temperature),
            str(fan_mode),
            str(current_flugastemp),
            str(current_exhfanspeed),
            str(pellet_speed),
            error_code,
            str(target_temperature) if support_setpoint else None,
        )
        return result
