import json
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    HVAC_MODE_FAN_ONLY,
    HVACAction,
    HVACMode,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, LOGGER

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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the climate platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtreaClimate(coordinator)], update_before_add=True)

class AtreaClimate(CoordinatorEntity, ClimateEntity):
    """Representation of an Atrea climate entity."""

    def __init__(self, coordinator):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_name = coordinator.data.get('name')
        self._attr_unique_id = f"amotionatrea_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.aatrea._host)},
            "name": coordinator.data.get('name'),
            "manufacturer": "Atrea",
            "model": coordinator.data.get('device_type'),
            "sw_version": coordinator.data.get('software_version'),
        }
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
    )

    @property
    def hvac_modes(self):
        return HVAC_MODES

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 10

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
    
    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.coordinator.data.get('current_temperature')

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.coordinator.data.get('setpoint')

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        self._attr_mode = self.coordinator.data.get('ui_info_data').get('unit').get('season_current')
        if self._attr_mode == "HEATING":
            return HVACMode.HEAT
        elif self._attr_mode == "NON_HEATING":
            return HVACMode.COOL
        elif self._attr_mode == "auto":
            return HVACMode.AUTO
        return HVACMode.OFF
    
    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            control = json.dumps({'variables': {'temp_request': temperature}})
            response_id = await self.coordinator.aatrea.send('{ "endpoint": "control", "args": %s }' % control)
            LOGGER.debug("TEMP %s" % response_id)
            await self.coordinator.aatrea.update(response_id)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        mode = 'HEATING' if hvac_mode == HVACMode.HEAT else 'NON_HEATING' if hvac_mode == HVACMode.COOL else 'OFF'
        await self.coordinator.aatrea.set_mode(mode)
        await self.coordinator.async_request_refresh()


    @property
    def name(self):
        """Return the name of this Thermostat."""
        return self._attr_name

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac i.e. heat, cool, idle."""
        if not self._attr_mode:
            return HVACAction.OFF
        if self._attr_mode == "HEATING":
            return HVACAction.HEATING
        elif self._attr_mode == "NON_HEATING":
            return HVACAction.COOLING
        return HVACAction.IDLE

    # @property
    # def state(self):
    #     """Return the current state."""
    #     # state = self._atrea.status.get('current_hvac_mode')
    #     state = self._attr_mode
    #     if state is None:
    #         LOGGER.warning("current_hvac_mode is None")
    #         return "unknown"
    #     return state

    # def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
    #     """Set new target hvac mode."""
    #     pass



    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self.coordinator.aatrea.set_temperature(temperature)
            await self.coordinator.async_request_refresh()

    @property
    def fan_mode(self):
        """Return the fan mode."""
        fan_mode = self.coordinator.data.get('ui_info_data',{}).get('requests',{}).get('fan_power_req')
        if fan_mode is None:
            return None
        return str(round(fan_mode, -1))

    @property
    def fan_modes(self):
        return ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.coordinator.aatrea.set_fan_mode(fan_mode)
        await self.coordinator.async_request_refresh()

# import time
# import logging
# import requests
# from websockets.sync.client import connect
# import json
# import asyncio

# from homeassistant.util import Throttle
# from homeassistant.core import HomeAssistant
# from homeassistant.config_entries import ConfigEntry
# from homeassistant.helpers.device_registry import DeviceInfo
# from typing import Callable, Any
# from homeassistant.components.climate.const import HVACAction

# from . import AmotionAtreaCoordinator
# from homeassistant.helpers.update_coordinator import CoordinatorEntity

# #from http.client import HTTPConnection
# #HTTPConnection.debuglevel = 1

# from homeassistant.components.climate import (
#     ATTR_HVAC_MODE,
#     ClimateEntity,
#     ClimateEntityFeature,
#     HVACMode,
# )

# from homeassistant.const import (
#     CONF_NAME,
#     CONF_HOST,
#     CONF_PASSWORD,
#     CONF_USERNAME,
#     TEMP_CELSIUS,
#     ATTR_TEMPERATURE
# )

# from homeassistant.components.climate.const import (
#     HVAC_MODE_OFF,
#     HVAC_MODE_AUTO,
#     HVAC_MODE_FAN_ONLY,
# )

# from .const import (
#     DOMAIN,
#     LOGGER,
#     SUPPORT_FLAGS,
#     STATE_UNKNOWN,
#     CONF_FAN_MODES,
#     CONF_PRESETS,
#     DEFAULT_FAN_MODE_LIST,
#     ALL_PRESET_LIST,
#     HVAC_MODES,
# )
# async def async_setup_entry(
#     hass: HomeAssistant,
#     entry: ConfigEntry,
#     async_add_entities: Callable
# ):
#     sensor_name = entry.data.get(CONF_NAME)
#     if sensor_name is None:
#         sensor_name = "aatrea"


#     coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
#     entities: list[AAtreaDevice] = [AAtreaDevice(coordinator, entry, sensor_name)]
#     async_add_entities(entities)


# class AAtreaDevice(
#     CoordinatorEntity[AmotionAtreaCoordinator], ClimateEntity
# ):

#     _attr_supported_features = (
#         ClimateEntityFeature.FAN_MODE
#         | ClimateEntityFeature.TARGET_TEMPERATURE
#     )

#     def __init__(self, coordinator, entry, sensor_name):
#         super().__init__(coordinator)
#         self._atrea = coordinator.aatrea
#         self._attr_unique_id = "%s-%s" % (sensor_name, entry.data.get(CONF_HOST))
#         self.updatePending = False
#         self._name = sensor_name

#         # Fetch device type and software version
#         self._device_type = None
#         self._software_version = None
#         asyncio.create_task(self._fetch_device_info())

#         self._attr_device_info = DeviceInfo(
#             identifiers={(DOMAIN, self._attr_unique_id)},
#             manufacturer="Atrea",
#             model=self._device_type,
#             name=self._name,
#             sw_version=self._software_version,
#         )

#         self._state = None
#         self._mode = None
#         self._current_hvac_mode = HVAC_MODE_AUTO

#     async def _fetch_device_info(self):
#         """Fetch device type and software version from the Atrea unit."""
#         device_type = None
#         software_version = None

#         try:
#             # Fetch device type from discovery endpoint
#             discovery_response = await self._atrea.fetch("discovery")
#             if isinstance(discovery_response, dict):
#                 device_type = discovery_response.get('response', {}).get('type')

#             # Fetch software version from version endpoint
#             version_response = await self._atrea.fetch("version")
#             if isinstance(version_response, dict):
#                 software_version = version_response.get('response', {}).get('GATEWAY', {}).get('version')

#         except Exception as e:
#             LOGGER.error(f"Error fetching device info: {e}")

#         self._device_type = device_type
#         self._software_version = software_version

#         # Update device info
#         self._attr_device_info = DeviceInfo(
#             identifiers={(DOMAIN, self._attr_unique_id)},
#             manufacturer="Atrea",
#             model=self._device_type,
#             name=self._name,
#             sw_version=self._software_version,
#         )
#         self.async_write_ha_state()

#     @property
#     def temperature_unit(self):
#         return TEMP_CELSIUS




#     @property
#     def hvac_mode(self) -> HVACMode:
#         """Return hvac operation ie. heat, cool mode.

#         Need to be one of HVAC_MODE_*.
#         """
#         if self._mode == 2:
#             return HVACMode.HEAT_COOL
#         return HVACMode.HEAT_COOL

#     @property
#     def name(self):
#         """Return the name of this Thermostat."""
#         return self._name

#     @property
#     def hvac_action(self) -> HVACAction:
#         """Return current hvac i.e. heat, cool, idle."""
#         if not self._mode:
#             return HVACAction.OFF
#         if self._state:
#             return HVACAction.HEATING
#         return HVACAction.IDLE



#     @property
#     def hvac_modes(self):
#         return HVAC_MODES

#     @property
#     def state(self):
#         """Return the current state."""
#         state = self._atrea.status.get('current_hvac_mode')
#         if state is None:
#             LOGGER.warning("current_hvac_mode is None")
#             return "unknown"
#         return state

#     def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
#         """Set new target hvac mode."""
#         pass


#     @property
#     def current_temperature(self):
#         """Return the current temperature."""
#         current_temp = self._atrea.status.get('current_temperature')
#         if current_temp is None:
#             LOGGER.warning("current_temperature is None")
#             return None
#         return current_temp

#     @property
#     def target_temperature(self):
#         """Return the temperature we try to reach."""
#         target_temp = self._atrea.status.get('setpoint')
#         if target_temp is None:
#             LOGGER.warning("setpoint is None")
#             return None
#         return target_temp

#     async def async_set_temperature(self, **kwargs):
#         """Set new target temperature."""
#         # TODO move to AmotionAtrea set_temperature?
#         control = json.dumps({'variables': {'temp_request': kwargs.get(ATTR_TEMPERATURE)}})
#         response_id = await self._atrea.send('{ "endpoint": "control", "args": %s }' % control)
#         LOGGER.debug("TEMP %s" % response_id)
#         await self._atrea.update(response_id)

#     @property
#     def fan_mode(self):
#         """Return the fan mode."""
#         fan_mode = self._atrea.status.get('fan_mode')
#         if fan_mode is None:
#             return None
#         return str(round(fan_mode, -1))

#     @property
#     def fan_modes(self):
#         return ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]

#     async def async_set_fan_mode(self, fan_mode):
#         """Set new target fan mode."""
#         await self._atrea.set_fan_mode(fan_mode)

