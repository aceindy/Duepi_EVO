"""Unit tests for climate hvac_action mapping."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from homeassistant.components.climate import HVACAction, HVACMode

from custom_components.duepi_evo.climate import DuepiEvoClimateEntity


pytestmark = [pytest.mark.usefixtures("enable_custom_integrations")]


def _entity_with_state(state: SimpleNamespace | None) -> DuepiEvoClimateEntity:
    """Create a minimal climate entity bound to a specific coordinator state."""
    entity = DuepiEvoClimateEntity.__new__(DuepiEvoClimateEntity)
    entity.coordinator = SimpleNamespace(data=state)
    return entity


@pytest.mark.parametrize(
    ("state", "expected_action"),
    [
        (None, HVACAction.OFF),
        (
            SimpleNamespace(
                burner_status="Flame On",
                heating=True,
                hvac_mode=HVACMode.HEAT,
            ),
            HVACAction.HEATING,
        ),
        (
            SimpleNamespace(
                burner_status="Cooling down",
                heating=False,
                hvac_mode=HVACMode.HEAT,
            ),
            HVACAction.IDLE,
        ),
        (
            SimpleNamespace(
                burner_status="Eco idle",
                heating=False,
                hvac_mode=HVACMode.HEAT,
            ),
            HVACAction.IDLE,
        ),
        (
            SimpleNamespace(
                burner_status="Cleaning",
                heating=False,
                hvac_mode=HVACMode.HEAT,
            ),
            HVACAction.IDLE,
        ),
        (
            SimpleNamespace(
                burner_status="Off",
                heating=False,
                hvac_mode=HVACMode.OFF,
            ),
            HVACAction.OFF,
        ),
    ],
)
def test_hvac_action_mapping(
    state: SimpleNamespace | None,
    expected_action: HVACAction,
) -> None:
    """HVAC action should reflect the key heating, idle, and off combinations."""
    entity = _entity_with_state(state)

    assert entity.hvac_action == expected_action


def test_set_temperature_keeps_commanded_value_without_setpoint_feedback() -> None:
    """No-feedback stoves should keep a successful command instead of reverting to fallback."""
    captured: dict[str, float] = {}

    def set_temperature(target_temperature: float) -> None:
        captured["target_temperature"] = target_temperature

    async def async_add_executor_job(func, *args):
        return func(*args)

    async def refresh_without_feedback() -> None:
        coordinator.data = SimpleNamespace(target_temp_c=None)

    coordinator = SimpleNamespace(
        data=SimpleNamespace(target_temp_c=None),
        client=SimpleNamespace(set_temperature=set_temperature),
        async_request_refresh=refresh_without_feedback,
    )
    entity = DuepiEvoClimateEntity.__new__(DuepiEvoClimateEntity)
    entity.coordinator = coordinator
    entity.hass = SimpleNamespace(async_add_executor_job=async_add_executor_job)
    entity._name = "Duepi EVO"
    entity._no_feedback = 16.0

    asyncio.run(entity.async_set_temperature(temperature=24))

    assert captured["target_temperature"] == 24.0
    assert entity.target_temperature == 24.0
