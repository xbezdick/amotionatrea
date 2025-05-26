import json
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.climate.const import HVACAction

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.climate import (
    ClimateEntity,
    HVACMode,
)

from homeassistant.const import (
    CONF_NAME,
    UnitOfTemperature,
    ATTR_TEMPERATURE
)

from . import AmotionAtreaCoordinator
from .const import (
    DOMAIN,
    LOGGER,
    SUPPORT_FLAGS,
    DEFAULT_FAN_MODE_LIST,
    HVAC_MODES,
)
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable
):
    sensor_name = entry.data.get(CONF_NAME)

    coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AAtreaDevice] = [AAtreaDevice(coordinator, sensor_name)]
    async_add_entities(entities, update_before_add=True)


class AAtreaDevice(
    CoordinatorEntity[AmotionAtreaCoordinator], ClimateEntity
):
    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_name):
        super().__init__(coordinator)
        self._atrea = coordinator.aatrea
        self._attr_name = self._atrea.name
        self._attr_unique_id = sensor_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._atrea.name)},
            manufacturer=self._atrea.brand,
            model=self._atrea.model,
            name=self._atrea.name,
            sw_version=self._atrea.sw_version,
            serial_number=self._atrea.serial,
        )

        self._state = None
        self._mode = None
        self._current_hvac_mode = HVACMode.AUTO

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        FIXME this should be returning based on UI control scheme
        """
        match self._atrea.status['season_current']:
            case "HEATING":
                return HVACMode.HEAT
            case "NON_HEATING":
                return HVACMode.COOL
            case "auto":
                return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._attr_name

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac i.e. heat, cool, idle."""
        match self._atrea.status['season_current']:
            case "HEATING":
                return HVACAction.HEATING
            case "NON_HEATING":
                return HVACAction.COOLING
            case "auto":
                return HVACAction.AUTO
        return HVACMode.OFF

    @property
    def hvac_modes(self):
        return HVAC_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._atrea.status['current_temperature']

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._atrea.status['setpoint']

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._atrea.set_fan_mode(kwargs.get(ATTR_TEMPERATURE))
        await self.coordinator.async_request_refresh()


    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        await self._atrea.set_hvac_mode(hvac_mode)
        await self.coordinator.async_request_refresh()

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return str(round(self._atrea.status['fan_mode'], -1))

    @property
    def fan_modes(self):
        return DEFAULT_FAN_MODE_LIST

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._atrea.set_fan_mode(fan_mode)
        await self.coordinator.async_request_refresh()
