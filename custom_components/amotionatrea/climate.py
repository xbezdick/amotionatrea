import time
import logging
import requests
from websockets.sync.client import connect
import json

from homeassistant.util import Throttle
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from typing import Callable, Any
from homeassistant.components.climate.const import HVACAction

from . import AmotionAtreaCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

#from http.client import HTTPConnection
#HTTPConnection.debuglevel = 1

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE
)

from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
)

from .const import (
    DOMAIN,
    LOGGER,
    SUPPORT_FLAGS,
    STATE_UNKNOWN,
    CONF_FAN_MODES,
    CONF_PRESETS,
    DEFAULT_FAN_MODE_LIST,
    ALL_PRESET_LIST,
    HVAC_MODES,
)
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable
):
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "aatrea"


    coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AAtreaDevice] = [AAtreaDevice(coordinator, entry, sensor_name)]
    async_add_entities(entities)


class AAtreaDevice(
    CoordinatorEntity[AmotionAtreaCoordinator], ClimateEntity
):

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(self, coordinator, entry, sensor_name):
        super().__init__(coordinator)
        self._atrea = coordinator.aatrea
        self._attr_unique_id = "%s-%s" % (sensor_name, entry.data.get(CONF_HOST))
        self.updatePending = False
        self._name = sensor_name
        # fixme - provide this from AmotionAtrea
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Atrea",
            model="TODOFIXME",
            name=self._name,
            sw_version="FIXME",
        )
        LOGGER.debug(self._attr_device_info)
        LOGGER.debug(self._attr_unique_id)

        self._state = None
        self._mode = None
        self._current_hvac_mode = HVAC_MODE_AUTO

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS




    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._mode == 2:
            return HVACMode.HEAT_COOL
        return HVACMode.HEAT_COOL

    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._name

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac i.e. heat, cool, idle."""
        if not self._mode:
            return HVACAction.OFF
        if self._state:
            return HVACAction.HEATING
        return HVACAction.IDLE



    @property
    def hvac_modes(self):
        return HVAC_MODES

    @property
    def state(self):
        return self._atrea.status['current_hvac_mode']

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        pass


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
        # TODO move to AmotionAtrea set_temperature?
        control = json.dumps({'variables': {'temp_request': kwargs.get(ATTR_TEMPERATURE)}})
        response_id = await self._atrea.send('{ "endpoint": "control", "args": %s }' % control)
        LOGGER.debug("TEMP %s" % response_id)
        await self._atrea.update(response_id)

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return str(round(self._atrea.status['fan_mode'], -1))

    @property
    def fan_modes(self):
        return ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._atrea.set_fan_mode(fan_mode)

