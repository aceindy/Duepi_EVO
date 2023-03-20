"""Platform for sensor integration."""
from __future__ import annotations

import aiohttp
import async_timeout
import socket
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    TEMP_CELSIUS,
    REVOLUTIONS_PER_MINUTE
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

get_flugastemp  = "\x1bRD000056&"  #--> Flugas temperature  0085002D& ~133 degs
get_fanspeed    = "\x1bREF0006D&"  #--> fan speed 00AF0047&  ~1750 rpm

async def async_setup_platform(hass, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Setup the Duepi EVO"""
    session = async_get_clientsession(hass)
    entities = []
    entities.append(FluGasSensor(session, config))
    entities.append(ExhFanSpeedSensor(session, config))
    async_add_entities(entities, False)

class FluGasSensor(SensorEntity):

    def __init__(self, session, config) -> None:
        """Initialize the DuepiEvoDevice."""
        self._session = session
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._flugas_temperature = None

    _attr_name = "Flugas Temperature"
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = 199
        _LOGGER.debug(
            "Flugas temp read %s", self._attr_native_value
        )

class ExhFanSpeedSensor(SensorEntity):

    def __init__(self, session, config) -> None:
        """Initialize the DuepiEvoDevice."""
        self._session = session
        self._name = config.get(CONF_NAME)
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._exhaust_fan_speed = None

    _attr_name = "Exhaust fan speed"
    _attr_native_unit_of_measurement = REVOLUTIONS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = 1099
        _LOGGER.debug(
            "Exhaust fan speed read %s",self._attr_native_value
        )
