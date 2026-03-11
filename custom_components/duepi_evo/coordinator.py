"""Coordinator for Duepi EVO polling and command-side refresh."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import DuepiEvoClient, DuepiEvoClientError, DuepiEvoState
from .const import AUTO_RESET_ERRORS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DuepiEvoCoordinator(DataUpdateCoordinator[DuepiEvoState]):
    """Central coordinator that owns a DuepiEvoClient."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DuepiEvoClient,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client
        self.name = name

    async def _async_update_data(self) -> DuepiEvoState:
        """Fetch latest data from the stove."""
        try:
            state = await self.hass.async_add_executor_job(self.client.fetch_state)
            if self.client.auto_reset and state.error_code in AUTO_RESET_ERRORS:
                await self.hass.async_add_executor_job(self.client.remote_reset, state.error_code)
                state = await self.hass.async_add_executor_job(self.client.fetch_state)
            return state
        except DuepiEvoClientError as err:
            raise UpdateFailed(str(err)) from err
