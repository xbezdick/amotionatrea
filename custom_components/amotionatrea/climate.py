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
    MIN_TIME_BETWEEN_SCANS,
    SUPPORT_FLAGS,
    STATE_UNKNOWN,
    CONF_FAN_MODES,
    CONF_PRESETS,
    DEFAULT_FAN_MODE_LIST,
    ALL_PRESET_LIST,
    HVAC_MODES,
)
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "aatrea"

    hass.data[DOMAIN][entry.entry_id]["climate"] = AAtreaDevice(hass, entry, sensor_name)
    async_add_entities([hass.data[DOMAIN][entry.entry_id]["climate"]])


class AAtreaDevice(ClimateEntity):

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(self, hass, entry, sensor_name):
        super().__init__()
        self.data = hass.data[DOMAIN][entry.entry_id]
        self._session = self.data["session"]
        self._ws = self.data["ws"]
        self._host = entry.data.get(CONF_HOST)
        self._attr_unique_id = "%s-%s" % (sensor_name, entry.data.get(CONF_HOST))
        self.updatePending = False
        self._name = sensor_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Atrea",
            model="TODOFIXME",
            name=self._name,
            sw_version="FIXME",
        )
        self._state = None
        self._temperature = None
        self._setpoint = None
        self._mode = None
        self._current_hvac_mode = HVAC_MODE_AUTO
        #self._inside_temperature = None
        #self._outside_temperature = None
        #self._exhaust_temperature = None
        self._fan_mode = None

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
        return self._current_hvac_mode

#    @property
#    def extra_state_attributes(self):
#        attributes = {}
#        attributes["inside_temperature"] = self._inside_temperature
#        attributes["outside_temperature"] = self._outside_temperature
#        attributes["exhaust_temperature"] = self._exhaust_temperature
#        return attributes

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        pass


    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._setpoint

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        control = {'variables': {'temp_request': kwargs.get(ATTR_TEMPERATURE)}}
        await self.hass.async_add_executor_job(self._ws.send, '{ "endpoint": "control", "args": "%s" }' % json.dumps(control))
        r = await self.hass.async_add_executor_job(self._ws.recv())
        LOGGER.debug(r)

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        if self._fan_mode:
            return str(round(self._fan_mode, -1))
        return "0"

    @property
    def fan_modes(self):
        return ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        control = {'variables': {'fan_power_req': int(fan_mode)}}
        await self.hass.async_add_executor_job(self._ws.send, '{ "endpoint": "control", "args": "%s" }' % self._host, json.dumps(control))
        r = await self.hass.async_add_executor_job(self._ws.recv())
        LOGGER.debug(r)

    async def async_update(self):
        if not self.updatePending:
            self.updatePending = True
            await self.hass.async_add_executor_job(self._ws.send, '{ "endpoint": "ui_info", "args": null }')
            r = json.loads( await self.hass.async_add_executor_job(self._ws.recv()))
            LOGGER.debug(r)
            self._temperature = r['response']["unit"]["temp_sup"]
            #self._inside_temperature = r.json()['result']["unit"]["temp_ida"]
            #self._outside_temperature = r.json()['result']["unit"]["temp_oda"]
            #self._exhaust_temperature = r.json()['result']["unit"]["temp_eha"]
            self._fan_mode = r['response']["requests"]["fan_power_req"]
            self._setpoint = r['response']["requests"]["temp_request"]
            self.updatePending = False

