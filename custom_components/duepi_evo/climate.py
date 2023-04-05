"""
Climate support for Duepi-evo base pellet stoves.

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
import logging
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout
import socket
import voluptuous as vol

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
    TEMP_CELSIUS,
    REVOLUTIONS_PER_MINUTE
)

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

try:
    from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
except ImportError:
    from homeassistant.components.climate import (
        ClimateDevice as ClimateEntity,
        PLATFORM_SCHEMA,
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

# global constants
state_ack   = 0x00000020
state_eco   = 0x10000000
state_clean = 0x04000000
state_cool  = 0x08000000
state_off   = 0x00000020
state_on    = 0x02000000
state_start = 0x01000000

get_errorstate  = "\x1bRDA00067&"
get_exhfanspeed = "\x1bREF0006D&"
get_flugastemp  = "\x1bRD000056&" 
get_pelletspeed = "\x1bRD40005A&"
get_setpoint    = "\x1bRC60005B&"
get_status      = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"
get_powerLevel  = "\x1bRD300059&"

remote_reset    = "\x1bRD60005C&"

set_augercor    = "\x1bRD50005A&"
set_extractcor  = "\x1bRD50005B&"
set_temperature = "\x1bRF2xx0yy&"
set_pelletcor   = "\x1bRD50005B&"
set_powerLevel  = "\x1bRF00xx0yy&"
set_powerOff    = "\x1bRF000058&"
set_powerOn     = "\x1bRF001059&"


# Set to True for stoves that support setpoint retrieval
support_setpoint = False

async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Duepi EVO"""
    session = async_get_clientsession(hass)
    add_devices([DuepiEvoDevice(session, config)], True)

class DuepiEvoDevice(ClimateEntity):
    """Representation of a DuepiEvoDevice."""

    def __init__(self, session, config) -> None:
        """Initialize the DuepiEvoDevice."""
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
        self._fan_mode_map_rev = {value: key for key, value in self._fan_mode_map.items()}
        self._pellet_speed = None
        self._current_fan_mode = self._fan_modes

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        return True

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def target_temperature_step(self):
        # Indicate the target temperature step for this climate device
        return 1.0

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self._name

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        # Use environment temperature if set to None (bug)
        if self._target_temperature is None:
            self._target_temperature = int(self._current_temperature)-1
            _LOGGER.debug("%s Setpoint retrieval not supported by this stove, using _current_temperature %s -1",self._name,str(self._target_temperature - 1))
        return self._target_temperature

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "burner_status": self._burner_status,
            "error_code": self._error_code,
            "exh_fan_speed": f"{self._exhaust_fan_speed} {REVOLUTIONS_PER_MINUTE}",
            "flu_gas_temp": f"{self._flugas_temp} {TEMP_CELSIUS}",
            "pellet_speed": self._pellet_speed,
            "power_level" : self._fan_mode
        }

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def fan_mode(self):
        """Return the fan setting."""
        self._fan_mode = self._current_fan_mode
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def hvac_mode(self) -> str:
        """Return the current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return SUPPORT_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation."""
        if self._burner_status in ["Eco Idle"]:
            return CURRENT_HVAC_IDLE
        elif self._heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_OFF

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        _LOGGER.debug("%s setting fanSpeed to %s", self.name, str(fan_mode))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        codeHexStr = hex(88 + self._fan_mode_map[fan_mode])
        data_yy = set_powerLevel.replace("yy", codeHexStr[2:4])
        powerlevelHexStr = hex(self._fan_mode_map[fan_mode])
        data_xx = data_yy.replace("xx", powerlevelHexStr[2:3])
        sock.send(data_xx.encode())
        dataFromServer = sock.recv(10).decode()
        dataFromServer = dataFromServer[1:9]
        current_state = int(dataFromServer, 16)
        if not (state_ack & current_state):
            _LOGGER.error("%s: Unable to set fan mode to %s",self._name,str(fan_mode),)
        sock.close()
        self._fan_mode = fan_mode

    async def async_set_temperature(self, **kwargs) -> None:
        """Set target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            _LOGGER.debug("%s: Unable to use target temp", self._name)
            return

        _LOGGER.debug("%s: Set target temp to %s°C", self._name, str(target_temperature))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        setPointInt = int(target_temperature)
        codeHexStr = hex(setPointInt + 75)
        setPointHexStr = hex(setPointInt)
        # send RF2xx0yy
        data = set_temperature
        datayy = data.replace("yy", codeHexStr[2:4])
        dataxy = datayy.replace("xx", setPointHexStr[2:4])
        sock.send(dataxy.encode())
        dataFromServer = sock.recv(10).decode()
        dataFromServer = dataFromServer[1:9]
        current_state = int(dataFromServer, 16)
        if not (state_ack & current_state):
            _LOGGER.error("%s: Unable to set target temp to %s°C",self._name,str(target_temperature))
        sock.close()
        self._target_temperature = target_temperature

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("%s: Set hvac mode to %s", self.name, str(hvac_mode))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        if hvac_mode == "off":
            sock.send(set_powerOff.encode())
            dataFromServer = sock.recv(10).decode()
            dataFromServer = dataFromServer[1:9]
            current_state = int(dataFromServer, 16)
            if not (state_ack & current_state):
                _LOGGER.error("%s: unknown return value %s",self.name,dataFromServer)
            self._hvac_mode = HVAC_MODE_OFF
        elif hvac_mode == "heat":
            sock.send(set_powerOn.encode())
            dataFromServer = sock.recv(10).decode()
            dataFromServer = dataFromServer[1:9]
            current_state = int(dataFromServer, 16)
            if not (state_ack & current_state):
                _LOGGER.error("%s: unknown return value %s",self.name,dataFromServer)
            self._hvac_mode = HVAC_MODE_HEAT
        sock.close()

    async def async_update(self) -> None:
        """Update local data with data from stove."""
        data = await self.get_data(self)
        self._burner_status = data[0]
        self._current_temperature = data[1]
        self._current_fan_mode = data[2]
        self._flugas_temp = data[3]
        self._exhaust_fan_speed = data[4]
        self._pellet_speed = data[5]
        self._error_code = data[6]

        #Perform auto reset when running out of pellets (when enabled)
        if self._auto_reset and self._error_code == "Out of pellets":
            await self.remote_reset(self)

        #If unit support the target temperature, update it
        if support_setpoint == True:
            self._target_temperature = data[7]

        self._heating = True
        self._hvac_mode = HVAC_MODE_HEAT
        if self._burner_status == "Off":
            self._heating = False
            self._hvac_mode = HVAC_MODE_OFF
        elif self._burner_status in ["Cooling down"]:
            self._heating = True
            self._hvac_mode = HVAC_MODE_OFF

    @staticmethod
    async def get_data(self):
        global support_setpoint
        """Get the data from the stove"""
        try:
            with async_timeout.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((self._host, self._port))

                # Get Burner status
                sock.send(get_status.encode())
                dataFromServer = sock.recv(10).decode()
                dataFromServer = dataFromServer[1:9]
                current_state = int(dataFromServer, 16)
                if state_start & current_state:
                    status = "Ignition starting"
                elif state_on & current_state:
                    status = "Flame On"
                elif state_clean & current_state:
                    status = "Cleaning"
                elif state_eco & current_state:
                    status = "Eco Idle"
                elif state_cool & current_state:
                    status = "Cooling down"
                elif state_off & current_state:
                    status = "Off"
                else:
                    status = "Error"

                # Get Ambient temperature
                sock.send(get_temperature.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    current_temperature = int(dataFromServer[1:5], 16) / 10.0
                else:
                    current_temperature = 21.0

                # Get Fan mode (also called fan speed or power level)
                sock.send(get_powerLevel.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    fan_mode = int(dataFromServer[1:5], 16)
                else:
                    fan_mode = None

                # Get pellet speed
                sock.send(get_pelletspeed.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    pellet_speed = int(dataFromServer[1:5], 16)
                else:
                    pellet_speed = none

                # Get FluGas temperature
                sock.send(get_flugastemp.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    current_flugastemp = int(dataFromServer[1:5], 16)
                else:
                    current_flugastemp = none

                # Get Exhaust Fan speed
                sock.send(get_exhfanspeed.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    current_exhfanspeed = int(dataFromServer[1:5], 16) * 10
                else:
                    current_exhfanspeed = none

                # Get Error code
                sock.send(get_errorstate.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    error_code_decimal = int(dataFromServer[1:5], 16)
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
                    error_code =  "Defective pressure switch"
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
                sock.send(get_setpoint.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    target_temperature = int(dataFromServer[1:5], 16)
                if target_temperature != 0:
                    support_setpoint = True

        except asyncio.TimeoutError:
            _LOGGER.error("Error occurred while polling using host: %s", self._host)
            sock.close()
            return None

        finally:
            sock.close()

        result = [status, current_temperature, fan_mode, current_flugastemp, current_exhfanspeed, pellet_speed, error_code]
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
            str(target_temperature) if support_setpoint else None
        )

        return result

    @staticmethod
    async def remote_reset(self):
        _LOGGER.debug("%s: Out of pellets !!", self.name)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        sock.send(remote_reset.encode())
        dataFromServer = sock.recv(10).decode()
        dataFromServer = dataFromServer[1:9]
        current_state = int(dataFromServer, 16)
        sock.close()

        if not (state_ack & current_state):
            _LOGGER.error("%s: unknown return value %s",self.name,dataFromServer)
