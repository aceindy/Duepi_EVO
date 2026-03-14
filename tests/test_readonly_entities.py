"""Unit tests for Duepi EVO read-only sensor entities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.const import EntityCategory

from custom_components.duepi_evo.binary_sensor import async_setup_entry as async_setup_binary_sensor_entry
from custom_components.duepi_evo.client import DuepiEvoState
from custom_components.duepi_evo.climate import async_setup_entry as async_setup_climate_entry
from custom_components.duepi_evo.const import DOMAIN
from custom_components.duepi_evo.sensor import async_setup_entry as async_setup_sensor_entry


def _state(*, pressure_switch_active: bool | None = True) -> DuepiEvoState:
    """Build a representative Duepi EVO state snapshot."""
    return DuepiEvoState(
        burner_status="Flame On",
        error_code="All OK",
        exh_fan_speed_rpm=500,
        flu_gas_temp_c=200,
        pellet_speed=20,
        power_level="Low",
        pcb_temp_c=45,
        total_burn_time_h=500,
        burn_time_since_reset_h=42,
        pressure_switch_active=pressure_switch_active,
        current_temp_c=21.5,
        target_temp_c=23.0,
        hvac_mode=HVACMode.HEAT,
        heating=True,
    )


def _entry() -> SimpleNamespace:
    """Build a minimal config-entry-like object for entity setup."""
    return SimpleNamespace(
        entry_id="entry-1",
        unique_id="192.168.1.12:2000",
        data={
            "name": "Pellet Stove",
            "host": "192.168.1.12",
            "port": 2000,
        },
        options={},
    )


@pytest.mark.asyncio
async def test_sensor_setup_exposes_expected_read_only_entities() -> None:
    """Sensor platform should create all read-only diagnostic entities."""
    coordinator = SimpleNamespace(data=_state())
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
    entities: list = []

    await async_setup_sensor_entry(hass, _entry(), entities.extend)

    assert {entity.entity_description.key for entity in entities} == {
        "burner_status",
        "error_code",
        "exh_fan_speed",
        "flu_gas_temp",
        "pellet_speed",
        "power_level",
        "pcb_temp",
        "total_burn_time",
        "burn_time_since_reset",
    }
    values = {entity.entity_description.key: entity.native_value for entity in entities}
    assert values["burner_status"] == "Flame On"
    assert values["error_code"] == "All OK"
    assert values["exh_fan_speed"] == 500
    assert values["flu_gas_temp"] == 200
    assert values["pellet_speed"] == 20
    assert values["power_level"] == "Low"
    assert values["pcb_temp"] == 45
    assert values["total_burn_time"] == 500
    assert values["burn_time_since_reset"] == 42
    assert {
        entity._attr_unique_id
        for entity in entities
    } == {
        "192.168.1.12:2000:sensor:burner_status",
        "192.168.1.12:2000:sensor:error_code",
        "192.168.1.12:2000:sensor:exh_fan_speed",
        "192.168.1.12:2000:sensor:flu_gas_temp",
        "192.168.1.12:2000:sensor:pellet_speed",
        "192.168.1.12:2000:sensor:power_level",
        "192.168.1.12:2000:sensor:pcb_temp",
        "192.168.1.12:2000:sensor:total_burn_time",
        "192.168.1.12:2000:sensor:burn_time_since_reset",
    }
    assert all(
        entity.entity_description.entity_category is EntityCategory.DIAGNOSTIC
        for entity in entities
    )
    assert all(
        entity.device_info["identifiers"] == {("duepi_evo", "192.168.1.12:2000")}
        for entity in entities
    )


@pytest.mark.asyncio
async def test_binary_sensor_setup_maps_pressure_switch_state() -> None:
    """Binary sensor platform should expose the pressure switch as a bool."""
    coordinator = SimpleNamespace(data=_state(pressure_switch_active=True))
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
    entities: list = []

    await async_setup_binary_sensor_entry(hass, _entry(), entities.extend)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_description.key == "pressure_switch"
    assert entity.entity_description.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.is_on is True
    assert entity._attr_unique_id == "192.168.1.12:2000:binary_sensor:pressure_switch"
    assert entity.device_info["identifiers"] == {("duepi_evo", "192.168.1.12:2000")}

    coordinator.data = _state(pressure_switch_active=None)
    assert entity.is_on is None


@pytest.mark.asyncio
async def test_climate_sensor_and_binary_sensor_share_same_device() -> None:
    """All entities for one stove should attach to the same HA device."""
    coordinator = SimpleNamespace(data=_state())
    hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
    climate_entities: list = []
    sensor_entities: list = []
    binary_sensor_entities: list = []
    entry = _entry()

    await async_setup_climate_entry(hass, entry, climate_entities.extend)
    await async_setup_sensor_entry(hass, entry, sensor_entities.extend)
    await async_setup_binary_sensor_entry(hass, entry, binary_sensor_entities.extend)

    assert len(climate_entities) == 1
    shared_identifiers = {("duepi_evo", "192.168.1.12:2000")}
    assert climate_entities[0].device_info["identifiers"] == shared_identifiers
    assert sensor_entities[0].device_info["identifiers"] == shared_identifiers
    assert binary_sensor_entities[0].device_info["identifiers"] == shared_identifiers
    assert climate_entities[0].device_info["name"] == "Pellet Stove"
