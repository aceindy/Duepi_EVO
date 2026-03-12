"""Unit tests for climate hvac_action mapping."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from homeassistant.components.climate import HVACAction, HVACMode

from custom_components.duepi_evo.climate import DuepiEvoClimateEntity


pytestmark = [pytest.mark.usefixtures("enable_custom_integrations")]


def test_hvac_action_is_idle_while_cooling_down() -> None:
    """Cooling down should report idle action while staying in heat mode."""
    entity = DuepiEvoClimateEntity.__new__(DuepiEvoClimateEntity)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            burner_status="Cooling down",
            heating=False,
            hvac_mode=HVACMode.HEAT,
        )
    )

    assert entity.hvac_action == HVACAction.IDLE
