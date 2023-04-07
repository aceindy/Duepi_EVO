"""Climate support for Duepi-evo base pellet stoves.

configuration.yaml

climate:
    - platform: duepi_evo
        name: Duepi Evo
        host: <IP_ADDRESS>
        port: 23
        scan_interval: 10
        auto_reset: True
"""
import asyncio
import async_timeout
import logging
import socket
import voluptuous as vol
from typing import Any, Dict, List, Optional


from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    REVOLUTIONS_PER_MINUTE,
    TEMP_CELSIUS,
)

from homeassistant.util import slugify
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

try:
    from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
except ImportError:
    from homeassistant.components.climate import (
        PLATFORM_SCHEMA,
        ClimateDevice as ClimateEntity,
    )

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
"""
Supported hvac modes:

- HVAC_MODE_HEAT: Heat to a target temperature (schedule off)
- HVAC_MODE_OFF:  The device runs in a continuous energy savings mode. If
                  configured as one of the supported hvac modes this mode
                  can be used to activate the vacation mode
"""
SUPPORT_MODES = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

DEFAULT_NAME = "Duepi EVO"
DEFAULT_HOST = ""
DEFAULT_PORT = 23
DEFAULT_MIN_TEMP = 15.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_AUTO_RESET = False
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_AUTO_RESET = "auto_reset"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_AUTO_RESET, default=DEFAULT_AUTO_RESET): vol.Coerce(bool),
    }
)

# constants
STATE_ACK = 0x00000020
STATE_ECO = 0x10000000
STATE_CLEAN = 0x04000000
STATE_COOL = 0x08000000
STATE_OFF = 0x00000020
STATE_ON = 0x02000000
STATE_START = 0x01000000

GET_ERRORSTATE = "\x1bRDA00067&"
GET_EXHFANSPEED = "\x1bREF0006D&"
GET_FLUGASTEMP = "\x1bRD000056&"
GET_PELLETSPEED = "\x1bRD40005A&"
GET_SETPOINT = "\x1bRC60005B&"
GET_STATUS = "\x1bRD90005f&"
GET_TEMPERATURE = "\x1bRD100057&"
GET_POWERLEVEL = "\x1bRD300059&"

REMOTE_RESET = "\x1bRD60005C&"

SET_AUGERCOR = "\x1bRD50005A&"
SET_EXTRACTORCOR = "\x1bRD50005B&"
SET_TEMPERATURE = "\x1bRF2xx0yy&"
SET_PELLETCOR = "\x1bRD50005B&"
SET_POWERLEVEL = "\x1bRF00xx0yy&"
SET_POWEROFF = "\x1bRF000058&"
SET_POWERON = "\x1bRF001059&"


# Set to True for stoves that support setpoint retrieval
SUPPORT_SETPOINT = False


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    # Setup the Duepi EVO.
    session = async_get_clientsession(hass)
    add_devices([DuepiEvoDevice(session, config)], True)


class DuepiEvoDevice(ClimateEntity):
    # Representation of a DuepiEvoDevice.

    def __init__(self, session, config) -> None:
        # Initialize the DuepiEvoDevice.
        self._session = session
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._min_temp = config.get(CONF_MIN_TEMP)
        self._max_temp = config.get(CONF_MAX_TEMP)
        self._auto_reset = config.get(CONF_AUTO_RESET)
        self._current_temperature = None
        self._target_temperature = None
        self._heating = False
        self._burner_status = None
        self._flugas_temp = None
        self._error_code = None
        self._exhaust_fan_speed = None
        self._hvac_mode = CURRENT_HVAC_OFF
        self._fan_modes = ["Min", "Low", "Medium", "High", "Max"]
        self._fan_mode = self._fan_modes[2]
        self._fan_mode_map = {"Min": 1, "Low": 2, "Medium": 3, "High": 4, "Max": 5}
        self._fan_mode_map_rev = {
            value: key for key, value in self._fan_mode_map.items()
        }
        self._pellet_speed = None
        self._current_fan_mode = self._fan_mode

    @property
    def should_poll(self):
        # Polling needed for thermostat.
        return True

    @property
    def supported_features(self) -> int:
        # Return the list of supported features.
        return SUPPORT_FLAGS

    @property
    def target_temperature_step(self):
        # Indicate the target temperature step for this climate device
        return 1.0

    @property
    def temperature_unit(self):
        # Indicate the target temperature unit for this climate device
        return TEMP_CELSIUS

    @property
    def name(self) -> str:
        # Return the name of the thermostat.
        return self._name

    @property
    def target_temperature(self) -> Optional[float]:
        # Return the temperature we try to reach.
        # Use environment temperature if set to None (bug)
        if self._target_temperature is None:
            self._target_temperature = int(self._current_temperature) - 1
            _LOGGER.debug(
                "%s Setpoint retrieval not supported by this stove, using _current_temperature %s -1",
                self._name,
                str(self._target_temperature - 1),
            )
        return self._target_temperature

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "burner_status": self._burner_status,
            "error_code": self._error_code,
            "exh_fan_speed": f"{self._exhaust_fan_speed} {REVOLUTIONS_PER_MINUTE}",
            "flu_gas_temp": f"{self._flugas_temp} {TEMP_CELSIUS}",
            "pellet_speed": self._pellet_speed,
            "power_level": self._fan_mode,
        }

    @property
    def current_temperature(self) -> Optional[float]:
        # Return the current temperature.
        return self._current_temperature

    @property
    def hvac_mode(self) -> str:
        # Return the current operation mode.
        return self._hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        # Return the list of available hvac operation modes.
        return SUPPORT_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        # Return the current running hvac operation.
        if self._burner_status in ["Eco Idle"]:
            return CURRENT_HVAC_IDLE
        elif self._heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_OFF

    @property
    def min_temp(self) -> float:
        # Return the minimum temperature.
        return self._min_temp

    @property
    def max_temp(self) -> float:
        # Return the maximum temperature.
        return self._max_temp

    @property
    def fan_mode(self):
        # Return the fan setting.
        self._fan_mode = self._current_fan_mode
        return self._fan_mode

    @property
    def fan_modes(self):
        # Return the list of available fan modes.
        return self._fan_modes

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode == "":
            _LOGGER.error("%s: Unable to read fan mode [%s]", self._name, fan_mode)
            return

        _LOGGER.debug("%s setting fanSpeed to %s", self.name, fan_mode)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        code_hex_str = hex(88 + self._fan_mode_map[fan_mode])
        data_yy = SET_POWERLEVEL.replace("yy", code_hex_str[2:4])
        power_level_hex_str = hex(self._fan_mode_map[fan_mode])
        data_xx = data_yy.replace("xx", power_level_hex_str[2:3])
        sock.send(data_xx.encode())
        data_from_server = sock.recv(10).decode()
        data_from_server = data_from_server[1:9]
        current_state = int(data_from_server, 16)
        if not (STATE_ACK & current_state):
            _LOGGER.error("%s: Unable to set fan mode to %s", self._name, str(fan_mode))
        sock.close()
        self._current_fan_mode = self._fan_mode = fan_mode

    async def async_set_temperature(self, **kwargs) -> None:
        # Set target temperature.
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            _LOGGER.debug("%s: Unable to use target temp", self._name)
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        set_point_int = int(target_temperature)
        code_hex_str = hex(set_point_int + 75)
        set_point_hex_str = hex(set_point_int)
        data = SET_TEMPERATURE
        datayy = data.replace("yy", code_hex_str[2:4])
        dataxy = datayy.replace("xx", set_point_hex_str[2:4])
        sock.send(dataxy.encode())
        data_from_server = sock.recv(10).decode()
        data_from_server = data_from_server[1:9]
        current_state = int(data_from_server, 16)
        if not (STATE_ACK & current_state):
            _LOGGER.error(
                "%s: Unable to set target temp to %s°C",
                self._name,
                str(target_temperature),
            )
        sock.close()
        self._target_temperature = target_temperature
        _LOGGER.debug(
            "%s: Set target temp to %s°C", self._name, str(target_temperature)
        )

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        # Set new target hvac mode.
        _LOGGER.debug("%s: Set hvac mode to %s", self.name, str(hvac_mode))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        if hvac_mode == "off":
            sock.send(SET_POWEROFF.encode())
            data_from_server = sock.recv(10).decode()
            data_from_server = data_from_server[1:9]
            current_state = int(data_from_server, 16)
            if not (STATE_ACK & current_state):
                _LOGGER.error(
                    "%s: unknown return value %s", self.name, data_from_server
                )
            self._hvac_mode = HVAC_MODE_OFF
        elif hvac_mode == "heat":
            sock.send(SET_POWERON.encode())
            data_from_server = sock.recv(10).decode()
            data_from_server = data_from_server[1:9]
            current_state = int(data_from_server, 16)
            if not (STATE_ACK & current_state):
                _LOGGER.error(
                    "%s: unknown return value %s", self.name, data_from_server
                )
            self._hvac_mode = HVAC_MODE_HEAT
        sock.close()

    async def async_update(self) -> None:
        # Update local data with data from stove.
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

        if self._burner_status == "Off":
            self._heating = False
            self._hvac_mode = HVAC_MODE_OFF
        elif self._burner_status in ["Cooling down"]:
            self._heating = True
            self._hvac_mode = HVAC_MODE_OFF
        else:
            self._heating = True
            self._hvac_mode = HVAC_MODE_HEAT

        # Perform auto reset when running out of pellets or ignition failure (when enabled)
        if self._auto_reset:
            if (
                self._error_code == "Out of pellets"
                or self._error_code == "Ignition failure"
            ):
                await self.remote_reset()

    async def get_data(self, support_setpoint) -> None:
        # Get the data from the stove
        try:
            with async_timeout.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))

                # Get Burner status
                sock.send(GET_STATUS.encode())
                data_from_server = sock.recv(10).decode()
                data_from_server = data_from_server[1:9]
                currentstate = int(data_from_server, 16)
                if STATE_START & currentstate:
                    status = "Ignition starting"
                elif STATE_ON & currentstate:
                    status = "Flame On"
                elif STATE_CLEAN & currentstate:
                    status = "Cleaning"
                elif STATE_ECO & currentstate:
                    status = "Eco Idle"
                elif STATE_COOL & currentstate:
                    status = "Cooling down"
                elif STATE_OFF & currentstate:
                    status = "Off"
                else:
                    status = "Error"

                # Get Ambient temperature
                sock.send(GET_TEMPERATURE.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    current_temperature = int(data_from_server[1:5], 16) / 10.0
                else:
                    current_temperature = 21.0

                # Get Fan mode (also called fan speed or power level)
                sock.send(GET_POWERLEVEL.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    fan_mode = int(data_from_server[1:5], 16)
                else:
                    fan_mode = None

                # Get pellet speed
                sock.send(GET_PELLETSPEED.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    pellet_speed = int(data_from_server[1:5], 16)
                else:
                    pellet_speed = None

                # Get FluGas temperature
                sock.send(GET_FLUGASTEMP.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    current_flugastemp = int(data_from_server[1:5], 16)
                else:
                    current_flugastemp = None

                # Get Exhaust Fan speed
                sock.send(GET_EXHFANSPEED.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    current_exhfanspeed = int(data_from_server[1:5], 16) * 10
                else:
                    current_exhfanspeed = None

                # Get Error code
                sock.send(GET_ERRORSTATE.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    error_code_decimal = int(data_from_server[1:5], 16)
                if error_code_decimal == 0:
                    error_code = "All OK"
                elif error_code_decimal == 1:
                    error_code = "Ignition failure"
                elif error_code_decimal == 2:
                    error_code = "Defective suction"
                elif error_code_decimal == 3:
                    error_code = "Insufficient air intake"
                elif error_code_decimal == 4:
                    error_code = "Water temperature"
                elif error_code_decimal == 5:
                    error_code = "Out of pellets"
                elif error_code_decimal == 6:
                    error_code = "Defective pressure switch"
                elif error_code_decimal == 7:
                    error_code = "Unknown"
                elif error_code_decimal == 8:
                    error_code = "No current"
                elif error_code_decimal == 9:
                    error_code = "Exhaust motor failure"
                elif error_code_decimal == 10:
                    error_code = "Card surge"
                elif error_code_decimal == 11:
                    error_code = "Date expired"
                elif error_code_decimal == 12:
                    error_code = "Unknown"
                elif error_code_decimal == 13:
                    error_code = "Suction regulating sensor error"
                elif error_code_decimal == 14:
                    error_code = "Overheating"
                else:
                    error_code = None

                # Get Setpoint temperature
                sock.send(GET_SETPOINT.encode())
                data_from_server = sock.recv(10).decode()
                if len(data_from_server) != 0:
                    target_temperature = int(data_from_server[1:5], 16)

                # Validate the returned value
                if (
                    target_temperature != 0
                    and target_temperature < self._max_temp
                    and target_temperature > self._min_temp
                ):
                    support_setpoint = True

        except asyncio.TimeoutError:
            _LOGGER.error("Error occurred while polling using host: %s", self._host)
            sock.close()
            return None

        finally:
            sock.close()

        result = [
            status,
            current_temperature,
            fan_mode,
            current_flugastemp,
            current_exhfanspeed,
            pellet_speed,
            error_code,
        ]
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

    async def async_added_to_hass(self) -> None:
        # Run when entity about to be added.
        await super().async_added_to_hass()
        self.entity_id = f"climate.{slugify(self._name)}"

    async def remote_reset(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        sock.send(REMOTE_RESET.encode())
        data_from_server = sock.recv(10).decode()
        data_from_server = data_from_server[1:9]
        currentstate = int(data_from_server, 16)
        sock.close()

        if not (STATE_ACK & currentstate):
            _LOGGER.error("%s: unknown return value %s", self.name, data_from_server)
        else:
            _LOGGER.debug("%s: Out of pellets !!", self.name)
