"""Config flow for Duepi EVO."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .client import DuepiEvoClient, DuepiEvoClientError
from .const import (
    CONF_AUTO_RESET,
    CONF_INIT_COMMAND,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NOFEEDBACK,
    CONF_UNIQUE_ID,
    DEFAULT_AUTO_RESET,
    DEFAULT_HOST,
    DEFAULT_INIT_COMMAND,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_NOFEEDBACK,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIQUE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _scan_interval_to_seconds(value: Any) -> int:
    """Normalize scan interval to integer seconds."""
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


def _entry_unique_id(host: str, port: int) -> str:
    """Build config entry unique ID from host/port."""
    return f"{host}:{port}"


class DuepiEvoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duepi EVO."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return options flow."""
        return DuepiEvoOptionsFlow(config_entry)

    async def _async_validate_connection(self, data: dict[str, Any], options: dict[str, Any]) -> bool:
        """Validate host/port by polling once."""
        client = DuepiEvoClient(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            min_temp=float(options[CONF_MIN_TEMP]),
            max_temp=float(options[CONF_MAX_TEMP]),
            no_feedback=float(options[CONF_NOFEEDBACK]),
            auto_reset=bool(options[CONF_AUTO_RESET]),
            init_command=bool(options[CONF_INIT_COMMAND]),
        )

        try:
            await self.hass.async_add_executor_job(client.fetch_state)
            return True
        except DuepiEvoClientError:
            return False

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        defaults = {
            CONF_HOST: DEFAULT_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_NAME: DEFAULT_NAME,
            CONF_INIT_COMMAND: DEFAULT_INIT_COMMAND,
        }

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unique_id = _entry_unique_id(host, port)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: user_input[CONF_NAME],
                CONF_UNIQUE_ID: DEFAULT_UNIQUE_ID,
            }
            options = {
                CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
                CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
                CONF_AUTO_RESET: DEFAULT_AUTO_RESET,
                CONF_NOFEEDBACK: DEFAULT_NOFEEDBACK,
                CONF_INIT_COMMAND: bool(user_input[CONF_INIT_COMMAND]),
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            }

            if await self._async_validate_connection(data, options):
                return self.async_create_entry(
                    title=data[CONF_NAME],
                    data=data,
                    options=options,
                )

            errors["base"] = "cannot_connect"
            defaults.update(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_NAME, default=defaults[CONF_NAME]): str,
                vol.Required(CONF_INIT_COMMAND, default=defaults[CONF_INIT_COMMAND]): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: dict[str, Any]) -> config_entries.FlowResult:
        """Handle YAML import."""
        host = import_config[CONF_HOST]
        port = import_config[CONF_PORT]
        unique_id = _entry_unique_id(host, port)

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_NAME: import_config.get(CONF_NAME, DEFAULT_NAME),
            CONF_UNIQUE_ID: import_config.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID),
        }
        options = {
            CONF_MIN_TEMP: import_config.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            CONF_MAX_TEMP: import_config.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            CONF_AUTO_RESET: import_config.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET),
            CONF_NOFEEDBACK: import_config.get(CONF_NOFEEDBACK, DEFAULT_NOFEEDBACK),
            CONF_INIT_COMMAND: import_config.get(CONF_INIT_COMMAND, DEFAULT_INIT_COMMAND),
            CONF_SCAN_INTERVAL: _scan_interval_to_seconds(
                import_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        }

        if not await self._async_validate_connection(data, options):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title=data[CONF_NAME], data=data, options=options)


class DuepiEvoOptionsFlow(config_entries.OptionsFlow):
    """Handle Duepi EVO options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_MIN_TEMP: self._config_entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
            CONF_MAX_TEMP: self._config_entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
            CONF_AUTO_RESET: self._config_entry.options.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET),
            CONF_NOFEEDBACK: self._config_entry.options.get(CONF_NOFEEDBACK, DEFAULT_NOFEEDBACK),
            CONF_INIT_COMMAND: self._config_entry.options.get(CONF_INIT_COMMAND, DEFAULT_INIT_COMMAND),
            CONF_SCAN_INTERVAL: self._config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_MIN_TEMP, default=defaults[CONF_MIN_TEMP]): vol.Coerce(float),
                vol.Required(CONF_MAX_TEMP, default=defaults[CONF_MAX_TEMP]): vol.Coerce(float),
                vol.Required(CONF_AUTO_RESET, default=defaults[CONF_AUTO_RESET]): bool,
                vol.Required(CONF_NOFEEDBACK, default=defaults[CONF_NOFEEDBACK]): vol.Coerce(float),
                vol.Required(CONF_INIT_COMMAND, default=defaults[CONF_INIT_COMMAND]): bool,
                vol.Required(CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]): vol.All(
                    vol.Coerce(int), vol.Range(min=5)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
