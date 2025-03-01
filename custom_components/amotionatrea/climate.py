import json
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, LOGGER

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
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
        return UnitOfTemperature.CELSIUS 
    
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
        return str(int(fan_mode))  # Convert to int first to remove decimals

    @property
    def fan_modes(self):
        return ["0", "10", "20", "30", "35", "40", "45", "50",
                 "55", "60", "65", "70", "75", "80", "85", "90", "95", "100"]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.coordinator.aatrea.set_fan_mode(fan_mode)
        await self.coordinator.async_request_refresh()

