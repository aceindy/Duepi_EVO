"""Config flow tests for Duepi EVO."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL

from custom_components.duepi_evo.const import (
    CONF_AUTO_RESET,
    CONF_INIT_COMMAND,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NOFEEDBACK,
    CONF_UNIQUE_ID,
    DEFAULT_INIT_COMMAND,
    DEFAULT_UNIQUE_ID,
    DOMAIN,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


def _schema_fields(schema) -> set[str]:
    """Return field names from a voluptuous schema."""
    return {getattr(key, "schema", key) for key in schema.schema}


async def _create_user_entry(hass, *, host: str, init_command: bool):
    """Create a config entry through the user flow."""
    with patch(
        "custom_components.duepi_evo.config_flow.DuepiEvoConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: host,
                CONF_PORT: 2000,
                CONF_NAME: "Poele Pellets",
                CONF_INIT_COMMAND: init_command,
            },
        )

    assert result["type"] == "create_entry"
    entry = hass.config_entries.async_entries(DOMAIN)[-1]
    return result, entry


async def test_user_step_exposes_init_command_and_hides_unique_id(hass) -> None:
    """Initial UI flow should ask for init_command, not unique_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == "form"
    fields = _schema_fields(result["data_schema"])
    assert {CONF_HOST, CONF_PORT, CONF_NAME, CONF_INIT_COMMAND}.issubset(fields)
    assert CONF_UNIQUE_ID not in fields


async def test_user_flow_persists_init_command_and_backend_unique_id(hass) -> None:
    """User flow should store init_command in options and keep backend unique_id default."""
    result, entry = await _create_user_entry(
        hass,
        host="192.168.1.12",
        init_command=True,
    )

    assert result["options"][CONF_INIT_COMMAND] is True
    assert result["data"][CONF_UNIQUE_ID] == DEFAULT_UNIQUE_ID
    assert entry.unique_id == "192.168.1.12:2000"


async def test_user_flow_returns_cannot_connect_without_crashing(hass) -> None:
    """Failed validation should stay on the form with a cannot_connect error."""
    with patch(
        "custom_components.duepi_evo.config_flow.DuepiEvoConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.13",
                CONF_PORT: 2000,
                CONF_NAME: "Poele Pellets",
                CONF_INIT_COMMAND: True,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_opens_and_saves_init_command(hass) -> None:
    """Existing entries should be configurable and keep init_command editable."""
    _, entry = await _create_user_entry(
        hass,
        host="192.168.1.14",
        init_command=False,
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    fields = _schema_fields(result["data_schema"])
    assert {
        CONF_MIN_TEMP,
        CONF_MAX_TEMP,
        CONF_AUTO_RESET,
        CONF_NOFEEDBACK,
        CONF_INIT_COMMAND,
        CONF_SCAN_INTERVAL,
    }.issubset(fields)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MIN_TEMP: 17.0,
            CONF_MAX_TEMP: 29.0,
            CONF_AUTO_RESET: True,
            CONF_NOFEEDBACK: 18.0,
            CONF_INIT_COMMAND: True,
            CONF_SCAN_INTERVAL: 30,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_INIT_COMMAND] is True


async def test_import_flow_keeps_init_command_in_options(hass) -> None:
    """YAML import should keep init_command when creating the config entry."""
    with patch(
        "custom_components.duepi_evo.config_flow.DuepiEvoConfigFlow._async_validate_connection",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: "192.168.1.15",
                CONF_PORT: 2000,
                CONF_NAME: "Imported Stove",
                CONF_INIT_COMMAND: True,
            },
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_UNIQUE_ID] == DEFAULT_UNIQUE_ID
    assert result["options"][CONF_INIT_COMMAND] is True


async def test_user_flow_defaults_init_command_when_not_enabled(hass) -> None:
    """User flow should keep init_command false when the user leaves it disabled."""
    result, _entry = await _create_user_entry(
        hass,
        host="192.168.1.16",
        init_command=DEFAULT_INIT_COMMAND,
    )

    assert result["options"][CONF_INIT_COMMAND] is DEFAULT_INIT_COMMAND
