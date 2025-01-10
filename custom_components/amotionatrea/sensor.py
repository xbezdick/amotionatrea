from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from dataclasses import dataclass
from .const import DOMAIN, LOGGER

@dataclass(frozen=True)
class AtreaSensorEntityDescription(SensorEntityDescription):
    json_value: str | None = None
    data_key: str = 'unit'

ATREA_SENSORS: tuple[AtreaSensorEntityDescription, ...] = (
    AtreaSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        name="Outdoor Air Temperature",
        icon="mdi:home-import-outline",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_oda",
    ),
    AtreaSensorEntityDescription(
        key="inside_temperature",
        translation_key="inside_temperature",
        name="Indoor Air Temperature",
        icon="mdi:home-thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_ida",
    ),
    AtreaSensorEntityDescription(
        key="exhaust_temperature",
        translation_key="exaust_temperature",
        name="Exhaust Air Temperature",
        icon="mdi:home-export-outline",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_eha",
    ),
    AtreaSensorEntityDescription(
        key="supply_air_temperature",
        translation_key="supply_temperature",
        name="Supply Air Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_sup",
    ),
    AtreaSensorEntityDescription(
        key="fan_sup_factor",
        name="Supply Fan",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="fan_sup_factor",
    ),
    AtreaSensorEntityDescription(
        key="fan_eta_factor",
        name="Extract Fan",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="fan_eta_factor",
    ),
    AtreaSensorEntityDescription(
        key="season_current",
        name="Current Season",
        icon="mdi:calendar",
        json_value="season_current",
    ),
    AtreaSensorEntityDescription(
        key="work_regime",
        name="Work Regime",
        icon="mdi:air-filter",
        data_key="requests",
        json_value="work_regime",
    ),
)

class AtreaSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Atrea sensor."""

    def __init__(self, coordinator, description: AtreaSensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"amotionatrea_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.aatrea._host)},
            name=coordinator.data.get('name'),
            manufacturer="Atrea",
            model=coordinator.data.get('device_type'),
            sw_version=coordinator.data.get('software_version'),
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""

        data_key = self.entity_description.data_key
        value = self.coordinator.data.get('ui_info_data', {}).get(data_key, {}).get(self.entity_description.json_value)
        if value is None and self.entity_description.json_value:
            value = self.coordinator.data.get('ui_info_data', {}).get(self.entity_description.json_value)
        LOGGER.debug(f"Sensor {self._attr_name} native_value: {value}")
        return value


    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = self.coordinator.data
        LOGGER.debug(f"Sensor {self._attr_name} extra_state_attributes: {attributes}")
        return attributes
    
    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()
        
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [AtreaSensor(coordinator, description) for description in ATREA_SENSORS]
    async_add_entities(sensors, update_before_add=True)

# """Support for Amotion Atrea sensors."""
# import time
# import asyncio
# import logging
# import requests, websocket
# import json

# from collections.abc import Callable
# from dataclasses import dataclass

# from homeassistant.config_entries import ConfigEntry
# from homeassistant.const import (
#     CONF_NAME,
#     CONF_HOST,
#     UnitOfEnergy,
#     UnitOfTemperature,
#     PERCENTAGE,
# )
# from homeassistant.core import HomeAssistant, callback
# from homeassistant.helpers.device_registry import DeviceInfo
# from homeassistant.helpers.dispatcher import async_dispatcher_connect
# from homeassistant.helpers.entity import async_generate_entity_id
# from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from . import AmotionAtreaCoordinator
# from homeassistant.helpers.update_coordinator import CoordinatorEntity

# from homeassistant.components.sensor import (
#     SensorDeviceClass,
#     SensorEntity,
#     SensorEntityDescription,
#     SensorStateClass,
#     ENTITY_ID_FORMAT,
# )


# from .const import (
#     DOMAIN,
#     LOGGER,
# )


# @dataclass(frozen=True)
# class AtreaSensorEntityDescription(SensorEntityDescription):
#     json_value: str | None = None


# ATREA_SENSORS: tuple[AtreaSensorEntityDescription, ...] = (
#     AtreaSensorEntityDescription(
#         key="outside_temperature",
#         translation_key="outside_temperature",
#         name="Outdoor Air Temperature",
#         icon="mdi:home-import-outline",
#         native_unit_of_measurement=UnitOfTemperature.CELSIUS,
#         device_class=SensorDeviceClass.TEMPERATURE,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="temp_oda",
#     ),
#     AtreaSensorEntityDescription(
#         key="inside_temperature",
#         translation_key="inside_temperature",
#         name="Indoor Air Temperature",
#         icon="mdi:home-thermometer",
#         native_unit_of_measurement=UnitOfTemperature.CELSIUS,
#         device_class=SensorDeviceClass.TEMPERATURE,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="temp_ida",
#     ),
#     AtreaSensorEntityDescription(
#         key="exhaust_temperature",
#         translation_key="exaust_temperature",
#         name="Exhaust Air Temperature",
#         icon="mdi:home-export-outline",
#         native_unit_of_measurement=UnitOfTemperature.CELSIUS,
#         device_class=SensorDeviceClass.TEMPERATURE,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="temp_eha",
#     ),
#     AtreaSensorEntityDescription(
#         key="supply_air_temperature",
#         translation_key="supply_temperature",
#         name="Supply Air Temperature",
#         icon="mdi:thermometer",
#         native_unit_of_measurement=UnitOfTemperature.CELSIUS,
#         device_class=SensorDeviceClass.TEMPERATURE,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="temp_sup",
#     ),
#     AtreaSensorEntityDescription(
#         key="extract_temperature",
#         translation_key="extract_temperature",
#         name="Air Extract Temperature",
#         icon="mdi:thermometer",
#         native_unit_of_measurement=UnitOfTemperature.CELSIUS,
#         device_class=SensorDeviceClass.TEMPERATURE,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="temp_eta",
#     ),
#     AtreaSensorEntityDescription(
#         key="season_current",
#         translation_key="season_current",
#         name="Current season ",
#         icon="mdi:sun-snowflake-variant",
#         device_class=SensorDeviceClass.ENUM	,
#         options=["NON_HEATING", "HEATING"],
#         json_value="season_current",
#     ),
#     AtreaSensorEntityDescription(
#         key="fan_eta_factor",
#         name="Exhaust Fan",
#         native_unit_of_measurement=PERCENTAGE,
#         device_class=SensorDeviceClass.POWER_FACTOR,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="fan_eta_factor",
#     ),
#     AtreaSensorEntityDescription(
#         key="fan_sup_factor",
#         name="Suply Fan",
#         native_unit_of_measurement=PERCENTAGE,
#         device_class=SensorDeviceClass.POWER_FACTOR,
#         state_class=SensorStateClass.MEASUREMENT,
#         json_value="fan_sup_factor",
#     ),
# )


# async def async_setup_entry(
#     hass: HomeAssistant,
#     entry: ConfigEntry,
#     async_add_entities: Callable,
# ):
#     sensor_name = entry.data.get(CONF_NAME)
#     if sensor_name is None:
#         sensor_name = "aatrea"

#     coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
#     entities: list[AAtreaDeviceSensor] = [
#         AAtreaDeviceSensor(coordinator, entry, description, sensor_name)
#         for description in ATREA_SENSORS
#     ]
#     async_add_entities(entities)


# class AAtreaDeviceSensor(
#     CoordinatorEntity[AmotionAtreaCoordinator], SensorEntity
# ):

#     entity_description: AtreaSensorEntityDescription
#     _attr_has_entity_name = True

#     def __init__(
#         self,
#         coordinator,
#         entry,
#         description: AtreaSensorEntityDescription,
#         sensor_name,
#     ) -> None:
#         super().__init__(coordinator)
#         self._atrea = coordinator.aatrea
#         self.entity_description = description
#         self._name = sensor_name
#         self._attr_unique_id = "%s-%s-%s" % (sensor_name, entry.data.get(CONF_HOST), description.key)
#         self._device_unique_id = "%s-%s" % (sensor_name, entry.data.get(CONF_HOST))
#         # Initialize device type and software version
#         self._device_type = "Unknown"
#         self._software_version = "Unknown"
#         asyncio.create_task(self._fetch_device_info())

#         self._attr_device_info = DeviceInfo(
#             identifiers={(DOMAIN, self._device_unique_id)},
#             manufacturer="Atrea",
#             model=self._device_type,
#             name=self._name,
#             sw_version=self._software_version,
#         )
#         self.updatePending = False

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

#         self._device_type = device_type or "Unknown"
#         self._software_version = software_version or "Unknown"

#         # Update device info
#         self._attr_device_info = DeviceInfo(
#             identifiers={(DOMAIN, self._device_unique_id)},
#             manufacturer="Atrea",
#             model=self._device_type,
#             name=self._name,
#             sw_version=self._software_version,
#         )
#         self.async_write_ha_state()
        
#     @property
#     def native_value(self) -> float | None:
#         """Return the state of the sensor."""
#         LOGGER.debug("CALLED %s" % self._name)
#         return self._atrea.status[self.entity_description.json_value]
