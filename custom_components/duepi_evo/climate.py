"""Climate support for Duepi EVO pellet stoves."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    REVOLUTIONS_PER_MINUTE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .client import DuepiEvoClient, DuepiEvoClientError, DuepiEvoState
from .const import (
    ATTR_BURNER_STATUS,
    ATTR_ERROR_CODE,
    ATTR_EXH_FAN_SPEED,
    ATTR_FLU_GAS_TEMP,
    ATTR_PELLET_SPEED,
    ATTR_POWER_LEVEL,
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
    FAN_MODES,
    SUPPORT_MODES,
    climate_unique_id_from_entry_unique_id,
    entry_unique_id,
)
from .coordinator import DuepiEvoCoordinator
from .entity_migration import stable_yaml_fallback_unique_id

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): cv.positive_float,
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): cv.positive_float,
        vol.Optional(CONF_AUTO_RESET, default=DEFAULT_AUTO_RESET): cv.boolean,
        vol.Optional(CONF_NOFEEDBACK, default=DEFAULT_NOFEEDBACK): cv.positive_float,
        vol.Optional(CONF_UNIQUE_ID, default=DEFAULT_UNIQUE_ID): cv.string,
        vol.Optional(CONF_INIT_COMMAND, default=DEFAULT_INIT_COMMAND): cv.boolean,
    }
)

_YAML_DEPRECATION_LOGGED = False


def _scan_interval_to_seconds(value: Any) -> int:
    """Normalize scan interval to integer seconds."""
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


def _yaml_import_data(config: ConfigType) -> dict[str, Any]:
    """Build config-entry payload from YAML platform config."""
    return {
        CONF_HOST: config.get(CONF_HOST, DEFAULT_HOST),
        CONF_PORT: config.get(CONF_PORT, DEFAULT_PORT),
        CONF_NAME: config.get(CONF_NAME, DEFAULT_NAME),
        CONF_UNIQUE_ID: config.get(CONF_UNIQUE_ID, DEFAULT_UNIQUE_ID),
        CONF_MIN_TEMP: config.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
        CONF_MAX_TEMP: config.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
        CONF_AUTO_RESET: config.get(CONF_AUTO_RESET, DEFAULT_AUTO_RESET),
        CONF_NOFEEDBACK: config.get(CONF_NOFEEDBACK, DEFAULT_NOFEEDBACK),
        CONF_INIT_COMMAND: config.get(CONF_INIT_COMMAND, DEFAULT_INIT_COMMAND),
        CONF_SCAN_INTERVAL: _scan_interval_to_seconds(
            config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    }


def _coordinator_from_yaml(hass: HomeAssistant, data: dict[str, Any]) -> DuepiEvoCoordinator:
    """Create a coordinator from YAML values."""
    client = DuepiEvoClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        min_temp=float(data[CONF_MIN_TEMP]),
        max_temp=float(data[CONF_MAX_TEMP]),
        no_feedback=float(data[CONF_NOFEEDBACK]),
        auto_reset=bool(data[CONF_AUTO_RESET]),
        init_command=bool(data[CONF_INIT_COMMAND]),
    )
    return DuepiEvoCoordinator(
        hass=hass,
        client=client,
        name=data[CONF_NAME],
        update_interval=timedelta(seconds=int(data[CONF_SCAN_INTERVAL])),
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up legacy YAML platform with import-first strategy."""
    del discovery_info
    global _YAML_DEPRECATION_LOGGED

    import_data = _yaml_import_data(config)

    if not _YAML_DEPRECATION_LOGGED:
        _LOGGER.warning(
            "Configuration via climate platform is deprecated. "
            "Please migrate to UI config flow. YAML import will be attempted automatically."
        )
        _YAML_DEPRECATION_LOGGED = True

    try:
        flow_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_data,
        )
        result_type = flow_result.get("type")
        result_reason = flow_result.get("reason")

        if result_type == "create_entry":
            _LOGGER.info(
                "Imported YAML config for %s into config entries",
                import_data[CONF_HOST],
            )
            return

        if result_type == "abort" and result_reason in {
            "already_configured",
            "already_in_progress",
        }:
            return

        _LOGGER.warning(
            "YAML import did not complete cleanly (type=%s, reason=%s). "
            "Falling back to legacy in-place platform setup.",
            result_type,
            result_reason,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "YAML import flow failed for %s:%s (%s). Falling back to legacy setup.",
            import_data[CONF_HOST],
            import_data[CONF_PORT],
            err,
        )

    coordinator = _coordinator_from_yaml(hass, import_data)
    await coordinator.async_refresh()
    async_add_entities(
        [
            DuepiEvoClimateEntity(
                coordinator=coordinator,
                name=import_data[CONF_NAME],
                unique_id=stable_yaml_fallback_unique_id(
                    import_data[CONF_HOST],
                    import_data[CONF_PORT],
                ),
                min_temp=float(import_data[CONF_MIN_TEMP]),
                max_temp=float(import_data[CONF_MAX_TEMP]),
                no_feedback=float(import_data[CONF_NOFEEDBACK]),
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entity from config entry."""
    coordinator: DuepiEvoCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    config_entry_unique_id = entry.unique_id or entry_unique_id(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    unique_id = climate_unique_id_from_entry_unique_id(config_entry_unique_id)
    min_temp = float(entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
    max_temp = float(entry.options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))
    no_feedback = float(entry.options.get(CONF_NOFEEDBACK, DEFAULT_NOFEEDBACK))

    async_add_entities(
        [
            DuepiEvoClimateEntity(
                coordinator=coordinator,
                name=name,
                unique_id=unique_id,
                min_temp=min_temp,
                max_temp=max_temp,
                no_feedback=no_feedback,
            )
        ]
    )


class DuepiEvoClimateEntity(CoordinatorEntity[DuepiEvoCoordinator], ClimateEntity):
    """Duepi EVO climate entity backed by a DataUpdateCoordinator."""

    _attr_supported_features = SUPPORT_FLAGS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0

    def __init__(
        self,
        coordinator: DuepiEvoCoordinator,
        name: str,
        unique_id: str,
        min_temp: float,
        max_temp: float,
        no_feedback: float,
    ) -> None:
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = unique_id
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._no_feedback = no_feedback
        self._legacy_attr_warning_logged = False

    @property
    def name(self) -> str:
        """Return the display name."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Disable direct polling, coordinator handles updates."""
        return False

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return supported HVAC modes."""
        return SUPPORT_MODES

    @property
    def fan_modes(self) -> list[str]:
        """Return supported fan modes."""
        return FAN_MODES

    @property
    def min_temp(self) -> float:
        """Return min setpoint."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return max setpoint."""
        return self._max_temp

    @property
    def _state(self) -> DuepiEvoState | None:
        """Return cached coordinator state."""
        return self.coordinator.data

    @property
    def current_temperature(self) -> float | None:
        """Return current ambient temperature."""
        state = self._state
        if state is None:
            return None
        return state.current_temp_c

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        state = self._state
        if state and state.target_temp_c is not None:
            return state.target_temp_c
        return float(self._no_feedback)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        state = self._state
        if state is None:
            return HVACMode.OFF
        return state.hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        state = self._state
        if state is None:
            return HVACAction.OFF
        if state.burner_status in {"Eco idle", "Eco Idle", "Cooling down"}:
            return HVACAction.IDLE
        if state.heating:
            return HVACAction.HEATING
        if state.hvac_mode == HVACMode.HEAT:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def fan_mode(self) -> str:
        """Return active fan mode."""
        state = self._state
        if state is None:
            return FAN_MODES[0]
        return state.power_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose legacy attributes during transition period."""
        if not self._legacy_attr_warning_logged:
            _LOGGER.warning(
                "Legacy Duepi EVO climate attributes are deprecated and will be removed "
                "after two releases. Please use dedicated sensor entities instead."
            )
            self._legacy_attr_warning_logged = True

        state = self._state
        if state is None:
            return {
                ATTR_BURNER_STATUS: None,
                ATTR_ERROR_CODE: None,
                ATTR_EXH_FAN_SPEED: None,
                ATTR_FLU_GAS_TEMP: None,
                ATTR_PELLET_SPEED: None,
                ATTR_POWER_LEVEL: None,
            }

        return {
            ATTR_BURNER_STATUS: state.burner_status,
            ATTR_ERROR_CODE: state.error_code,
            ATTR_EXH_FAN_SPEED: (
                f"{state.exh_fan_speed_rpm} {REVOLUTIONS_PER_MINUTE}"
                if state.exh_fan_speed_rpm is not None
                else None
            ),
            ATTR_FLU_GAS_TEMP: (
                f"{state.flu_gas_temp_c} {UnitOfTemperature.CELSIUS}"
                if state.flu_gas_temp_c is not None
                else None
            ),
            ATTR_PELLET_SPEED: state.pellet_speed,
            ATTR_POWER_LEVEL: state.power_level,
        }

    async def async_added_to_hass(self) -> None:
        """Set stable entity_id based on configured name."""
        await super().async_added_to_hass()
        self.entity_id = f"climate.{slugify(self._name)}"

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode and refresh."""
        if not fan_mode:
            _LOGGER.error("%s: Unable to read fan mode [%s]", self._name, fan_mode)
            return

        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_fan_mode,
                fan_mode,
            )
        except DuepiEvoClientError as err:
            _LOGGER.error("%s: Unable to set fan mode to %s (%s)", self._name, fan_mode, err)
            return

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature and refresh."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            _LOGGER.debug("%s: Unable to use target temp", self._name)
            return

        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_temperature,
                float(target_temperature),
            )
        except DuepiEvoClientError as err:
            _LOGGER.error(
                "%s: Unable to set target temp to %s (%s)",
                self._name,
                target_temperature,
                err,
            )
            return

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode and refresh."""
        if hvac_mode not in SUPPORT_MODES:
            _LOGGER.error("%s: Unsupported HVAC mode %s", self._name, hvac_mode)
            return

        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.set_hvac_mode,
                hvac_mode,
            )
        except DuepiEvoClientError as err:
            _LOGGER.error("%s: Unable to set hvac mode to %s (%s)", self._name, hvac_mode, err)
            return

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on using HVAC heat mode."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off using HVAC off mode."""
        await self.async_set_hvac_mode(HVACMode.OFF)
