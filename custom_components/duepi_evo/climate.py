"""
Climate support for Duepi-evo base pellet stoves.

configuration.yaml

climate:
    - platform: duepi_evo
        name: Duepi Evo
        host: <IP_ADDRESS>
        port: 23
        scan_interval: 10
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
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
    }
)

# global constants
state_ack = 0x00000020
state_off = 0x00000020
state_start = 0x01000000
state_on = 0x02000000
state_clean = 0x04000000
state_cool = 0x08000000
state_eco = 0x10000000

get_status      = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"
get_setpoint    = "\x1bRC60005B&"
get_pelletspeed = "\x1bRD40005A&"
get_flugastemp  = "\x1bRD000056&" 
get_fanspeed    = "\x1bREF0006D&" 
get_errorstate  = "\x1bRDA00067&"

set_temperature = "\x1bRF2xx0yy&"
set_powerLevel = "\x1bRF00xx0yy&"
set_powerOff = "\x1bRF000058&"
set_powerOn = "\x1bRF001059&"
set_pelletcor = "\x1bRD50005B&"
set_extractcor = "\x1bRD50005B&"
set_augercor = "\x1bRD50005A&"

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
        self._current_temperature = None
        self._target_temperature = None
        self._heating = False
        self._burner_status = None
        self._flugas_temp = None
        self._error_code = None
        self._exhaust_fan_speed = None
        self._hvac_mode = CURRENT_HVAC_OFF
        self._fan_mode = None
        self._fan_modes = ["1", "2", "3", "4", "5"]
        self._current_fan_mode = self._fan_mode

    @staticmethod
    async def get_data(self):
        global support_setpoint
        """Get the data from the device"""
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

                # Get pellet speed
                sock.send(get_pelletspeed.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    fan_mode = int(dataFromServer[1:5], 16)
                else:
                    fan_mode = None

                '''
                # Get FluGas temperature
                RD000056& --> Flugas temperature ??
                            RD000056& 0085002D& ~133 degs
                '''
                sock.send(get_flugastemp.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    current_flugastemp = int(dataFromServer[1:5], 16)
                else:
                    current_flugastemp = none

                '''
                # Get Exhaust Fan speed
                REF0006D --> fan speed ??
                            REF0006D& 00AF0047&  ~1750 rpm
                '''
                sock.send(get_fanspeed.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    current_exhfanspeed = int(dataFromServer[1:5], 16) * 10
                else:
                    current_exhfanspeed = none

                '''
                # Get Error code
                get_errorstate  = "\x1bRDA00067&" 
                The returned values have the following format:
                    00xx00yy
                In the returned value, the xx byte represents the error code.
                The yy byte seems to be the error value appended with 0x20.
                '''
                sock.send(get_errorstate.encode())
                dataFromServer = sock.recv(10).decode()
                if len(dataFromServer) != 0:
                    error_code_decimal = int(dataFromServer[2:3], 16)
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

                sock.close()

        except asyncio.TimeoutError:
            _LOGGER.error("Error occurred while polling using host: %s", self._host)
            return None

        if support_setpoint == False:
            result = [status, current_temperature, fan_mode, current_flugastemp, current_exhfanspeed, error_code]
            _LOGGER.debug(
                "%s: Received burner: %s, Ambient temp: %s, Fan speed: %s, Flu gas temp: %s, Exh fan speed: %s, Error code: %s ",
                self._name,
                status,
                str(current_temperature),
                str(fan_mode),
                str(current_flugastemp),
                str(current_exhfanspeed),
                error_code
            )
        else:
            result = [status, current_temperature, fan_mode, current_flugastemp, current_exhfanspeed, error_code, target_temperature]
            _LOGGER.debug(
                "%s: Received burner: %s, Ambient temp: %s, Fan speed: %s, Flu gas temp: %s, Exh fan speed: %s, Error code: %s, Setpoint temp: %s",
                self._name,
                status,
                str(current_temperature),
                str(fan_mode),
                str(current_flugastemp),
                str(current_exhfanspeed),
                error_code,
                str(target_temperature)
            )

        return result

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        return True

    async def async_update(self) -> None:
        """Update local data with thermostat data."""
        data = await self.get_data(self)
        self._burner_status = data[0]
        self._current_temperature = data[1]
        self._fan_mode = data[2]
        self._flugas_temp = data[3]
        self._exhaust_fan_speed = data[4]
        self._error_code = data[5]
        if support_setpoint == True:
            self._target_temperature = data[6]

        self._heating = True
        self._hvac_mode = HVAC_MODE_HEAT
        if self._burner_status == "Off":
            self._heating = False
            self._hvac_mode = HVAC_MODE_OFF
        elif self._burner_status in ["Cooling down"]:
            self._heating = True
            self._hvac_mode = HVAC_MODE_OFF

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self._name

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "burner_status": self._burner_status,
            "Flug_gas_temp": f"{self._flugas_temp} {TEMP_CELSIUS}",
            "Exh_fan_speed": f"{self._exhaust_fan_speed} {REVOLUTIONS_PER_MINUTE}",
            "error_code": self._error_code
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
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        # Use environment temperature is set to None (bug)
        if self._target_temperature is None:
            self._target_temperature = int(self._current_temperature)
            _LOGGER.debug(
                "%s Setpoint retrieval not supported by this stove, using _current_temperature %s",
                self._name,
                str(self._target_temperature),
            )
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            _LOGGER.debug(
                "%s: Unable to use target temp", self._name
            )
            return
        _LOGGER.debug(
            "%s: Set target temp to %s°C", self._name, str(target_temperature)
        )

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
            _LOGGER.error(
                "%s: Unable to set target temp to %s°C",
                self._name,
                str(target_temperature),
            )
        sock.close()
        self._target_temperature = target_temperature

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
                _LOGGER.error(
                    "%s: unknown return value %s",
                    self.name,
                    dataFromServer,
                )
            self._hvac_mode = HVAC_MODE_OFF
        elif hvac_mode == "heat":
            sock.send(set_powerOn.encode())
            dataFromServer = sock.recv(10).decode()
            dataFromServer = dataFromServer[1:9]
            current_state = int(dataFromServer, 16)
            if not (state_ack & current_state):
                _LOGGER.error(
                    "%s: unknown return value %s",
                    self.name,
                    dataFromServer,
                )
            self._hvac_mode = HVAC_MODE_HEAT
        sock.close()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._current_fan_mode = fan_mode
        _LOGGER.debug("%s setting fanSpeed to %s", self.name, str(fan_mode))

        fan_speed = int(fan_mode)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((self._host, self._port))
        codeHexStr = hex(88 + fan_speed)
        data_yy = set_powerLevel.replace("yy", codeHexStr[2:4])
        powerlevelHexStr = hex(fan_speed)
        data_xx = data_yy.replace("xx", powerlevelHexStr[2:3])
        sock.send(data_xx.encode())
        dataFromServer = sock.recv(10).decode()
        dataFromServer = dataFromServer[1:9]
        current_state = int(dataFromServer, 16)
        if not (state_ack & current_state):
            _LOGGER.error(
                "%s: Unable to set fan mode to %s",
                self._name,
                str(fan_mode),
            )
        sock.close()
