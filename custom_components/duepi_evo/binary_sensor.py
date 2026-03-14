"""Dedicated binary sensors for Duepi EVO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import DuepiEvoState
from .const import (
    ATTR_PRESSURE_SWITCH,
    DEFAULT_NAME,
    DOMAIN,
    entry_unique_id,
)
from .coordinator import DuepiEvoCoordinator
from .device import build_device_info


@dataclass(frozen=True, kw_only=True)
class DuepiEvoBinarySensorDescription(BinarySensorEntityDescription):
    """Description of one Duepi EVO binary sensor."""

    value_fn: Callable[[DuepiEvoState], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[DuepiEvoBinarySensorDescription, ...] = (
    DuepiEvoBinarySensorDescription(
        key=ATTR_PRESSURE_SWITCH,
        name="Pressure Switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.pressure_switch_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Duepi EVO binary sensors from config entry."""
    coordinator: DuepiEvoCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    unique_base = entry.unique_id or entry_unique_id(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

    async_add_entities(
        [
            DuepiEvoBinarySensorEntity(
                coordinator=coordinator,
                description=description,
                name=name,
                unique_base=unique_base,
            )
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class DuepiEvoBinarySensorEntity(CoordinatorEntity[DuepiEvoCoordinator], BinarySensorEntity):
    """Coordinator-backed Duepi EVO binary sensor."""

    entity_description: DuepiEvoBinarySensorDescription

    def __init__(
        self,
        coordinator: DuepiEvoCoordinator,
        description: DuepiEvoBinarySensorDescription,
        name: str,
        unique_base: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_name = name
        self._unique_base = unique_base
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_base}:binary_sensor:{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the pressure switch state."""
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)

    @property
    def device_info(self):
        """Return the parent stove device information."""
        return build_device_info(self._unique_base, self._device_name)
