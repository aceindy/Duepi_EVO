"""Dedicated read-only sensors for Duepi EVO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import DuepiEvoState
from .const import (
    ATTR_BURNER_STATUS,
    ATTR_ERROR_CODE,
    ATTR_EXH_FAN_SPEED,
    ATTR_FLU_GAS_TEMP,
    ATTR_PELLET_SPEED,
    ATTR_POWER_LEVEL,
    CONF_UNIQUE_ID,
    DEFAULT_NAME,
    DEFAULT_UNIQUE_ID,
    DOMAIN,
)
from .coordinator import DuepiEvoCoordinator


@dataclass(frozen=True, kw_only=True)
class DuepiEvoSensorDescription(SensorEntityDescription):
    """Description of one Duepi EVO sensor."""

    value_fn: Callable[[DuepiEvoState], Any]


SENSOR_DESCRIPTIONS: tuple[DuepiEvoSensorDescription, ...] = (
    DuepiEvoSensorDescription(
        key=ATTR_BURNER_STATUS,
        name="Burner Status",
        value_fn=lambda state: state.burner_status,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_ERROR_CODE,
        name="Error Code",
        value_fn=lambda state: state.error_code,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_EXH_FAN_SPEED,
        name="Exhaust Fan Speed",
        native_unit_of_measurement="rpm",
        value_fn=lambda state: state.exh_fan_speed_rpm,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_FLU_GAS_TEMP,
        name="Flu Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda state: state.flu_gas_temp_c,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_PELLET_SPEED,
        name="Pellet Speed",
        value_fn=lambda state: state.pellet_speed,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_POWER_LEVEL,
        name="Power Level",
        value_fn=lambda state: state.power_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Duepi EVO sensors from config entry."""
    coordinator: DuepiEvoCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_base = f"{entry.entry_id}_{entry.data.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID)}"

    async_add_entities(
        [
            DuepiEvoSensorEntity(
                coordinator=coordinator,
                description=description,
                name=name,
                unique_base=unique_base,
            )
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class DuepiEvoSensorEntity(CoordinatorEntity[DuepiEvoCoordinator], SensorEntity):
    """Coordinator-backed Duepi EVO sensor."""

    entity_description: DuepiEvoSensorDescription

    def __init__(
        self,
        coordinator: DuepiEvoCoordinator,
        description: DuepiEvoSensorDescription,
        name: str,
        unique_base: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_base}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)
