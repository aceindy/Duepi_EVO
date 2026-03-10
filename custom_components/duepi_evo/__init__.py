"""Duepi EVO integration setup."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .client import DuepiEvoClient
from .const import (
    CONF_AUTO_RESET,
    CONF_INIT_COMMAND,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NOFEEDBACK,
    DEFAULT_AUTO_RESET,
    DEFAULT_INIT_COMMAND,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_NOFEEDBACK,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import DuepiEvoCoordinator
from .entity_migration import migrate_climate_entity_registry


def _build_client_from_entry(entry: ConfigEntry) -> DuepiEvoClient:
    """Build a client from a config entry."""
    return DuepiEvoClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        min_temp=float(entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)),
        max_temp=float(entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)),
        no_feedback=float(entry.options.get(CONF_NOFEEDBACK, DEFAULT_NOFEEDBACK)),
        auto_reset=bool(entry.options.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET)),
        init_command=bool(entry.options.get(CONF_INIT_COMMAND, DEFAULT_INIT_COMMAND)),
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Duepi EVO component."""
    del config
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duepi EVO from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    migrate_climate_entity_registry(er.async_get(hass), entry)

    client = _build_client_from_entry(entry)
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    coordinator = DuepiEvoCoordinator(
        hass=hass,
        client=client,
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
