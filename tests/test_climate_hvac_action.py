"""Unit tests for climate hvac_action mapping."""

from __future__ import annotations

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
