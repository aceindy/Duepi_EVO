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
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    TEMP_CELSIUS,
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

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE
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

# constants
state_ack = 0x00000020
state_off = 0x00000020
state_start = 0x01000000
state_on = 0x02000000
state_cool = 0x08000000
state_eco = 0x10000000

get_status = "\x1bRD90005f&"
get_temperature = "\x1bRD100057&"
set_temperature = "\x1bRF2xx0yy&"
set_powerLevel = "\x1bRF00x0yy&"
set_powerOff = "\x1bRF000058&"
set_powerOn = "\x1bRF001059&"

# pylint: disable=unused-argument
async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Duepi EVO"""
    session = async_get_clientsession(hass)
    add_devices([DuepiEvoDevice(session, config)], True)


# pylint: disable=too-many-instance-attributes
# pylint: disable=bad-staticmethod-argument
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
        self._burner_info = None
        self._hvac_mode = CURRENT_HVAC_OFF

    @staticmethod
    async def get_data(self):
        """Get the data from the device"""
        try:
            with async_timeout.timeout(5):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                    current_temperature = 0.0

                sock.close()

        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error occurred while polling using host: %s", self._host
            )
            return None

        result = [status, current_temperature]
        _LOGGER.debug(
            "%s: Received burner: %s, ambient temp: %s",
            self._name,
            status,
            str(current_temperature),
        )
        return result

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        return True

    async def async_update(self) -> None:
        """Update local data with thermostat data."""
        data = await self.get_data(self)
        self._burner_info = data[0]
        self._current_temperature = data[1]
        self._heating = self._burner_info in ["Flame On", "Ignition starting"]

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self) -> str:
        """Return the name of the thermostat."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the current state of the burner."""
        return {"burner_info": self._burner_info}

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
            self._target_temperature = self._current_temperature
            _LOGGER.debug(
                "%s Setpoint unknown, using _current_temperature %s",
                self._name,
                str(self._current_temperature),
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
            return
        _LOGGER.debug(
            "%s: Set target temp to %s°C", self._name, str(target_temperature)
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        if "Eco" in self._burner_info:
            return CURRENT_HVAC_IDLE
        elif self._heating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_OFF

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("%s: Set hvac mode to %s", self.name, str(hvac_mode))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self._host, self._port))
        if hvac_mode == "off":
            sock.send(set_powerOff.encode())
            dataFromServer = sock.recv(10).decode()
            self._hvac_mode = HVAC_MODE_OFF
        elif hvac_mode == "heat":
            sock.send(set_powerOn.encode())
            dataFromServer = sock.recv(10).decode()
            current_state = int(dataFromServer, 16)
            self._hvac_mode = HVAC_MODE_HEAT
        sock.close()
