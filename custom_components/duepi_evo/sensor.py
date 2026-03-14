"""Dedicated read-only sensors for Duepi EVO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import DuepiEvoState
from .const import (
    ATTR_BURNER_STATUS,
    ATTR_BURN_TIME_SINCE_RESET,
    ATTR_ERROR_CODE,
    ATTR_EXH_FAN_SPEED,
    ATTR_FLU_GAS_TEMP,
    ATTR_PCB_TEMP,
    ATTR_PELLET_SPEED,
    ATTR_POWER_LEVEL,
    ATTR_TOTAL_BURN_TIME,
    DEFAULT_NAME,
    DOMAIN,
    entry_unique_id,
)
from .coordinator import DuepiEvoCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class DuepiEvoSensorDescription(SensorEntityDescription):
    """Description of one Duepi EVO sensor."""

    value_fn: Callable[[DuepiEvoState], Any]


SENSOR_DESCRIPTIONS: tuple[DuepiEvoSensorDescription, ...] = (
    DuepiEvoSensorDescription(
        key=ATTR_BURNER_STATUS,
        name="Burner Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.burner_status,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_ERROR_CODE,
        name="Error Code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error_code,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_EXH_FAN_SPEED,
        name="Exhaust Fan Speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="rpm",
        value_fn=lambda state: state.exh_fan_speed_rpm,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_FLU_GAS_TEMP,
        name="Flu Gas Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda state: state.flu_gas_temp_c,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_PELLET_SPEED,
        name="Pellet Speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.pellet_speed,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_POWER_LEVEL,
        name="Power Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.power_level,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_PCB_TEMP,
        name="PCB Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda state: state.pcb_temp_c,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_TOTAL_BURN_TIME,
        name="Total Burn Time",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="h",
        value_fn=lambda state: state.total_burn_time_h,
    ),
    DuepiEvoSensorDescription(
        key=ATTR_BURN_TIME_SINCE_RESET,
        name="Burn Time Since Reset",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="h",
        value_fn=lambda state: state.burn_time_since_reset_h,
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
    unique_base = entry.unique_id or entry_unique_id(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

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
        self._device_name = name
        self._unique_base = unique_base
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_base}:sensor:{description.key}"

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)

    @property
    def device_info(self):
        """Return the parent stove device information."""
        return build_device_info(self._unique_base, self._device_name)
