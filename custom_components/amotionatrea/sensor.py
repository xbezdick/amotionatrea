"""Support for Amotion Atrea sensors."""
import time
import logging
import requests, websocket
import json

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfEnergy,
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmotionAtreaCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    ENTITY_ID_FORMAT,
)


from .const import (
    DOMAIN,
    LOGGER,
)


@dataclass(frozen=True)
class AtreaSensorEntityDescription(SensorEntityDescription):
    json_value: str | None = None


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
        key="fan_eta_factor",
        name="Exhaust Fan",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="fan_eta_factor",
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
        key="extract_temperature",
        translation_key="extract_temperature",
        name="Air Extract Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_eta",
    ),
    AtreaSensorEntityDescription(
        key="season_current",
        translation_key="season_current",
        name="Current season ",
        icon="mdi:sun-snowflake-variant",
        device_class=SensorDeviceClass.ENUM	,
        options=["NON_HEATING", "HEATING"],
        json_value="season_current",
    ),
    AtreaSensorEntityDescription(
        key="fan_sup_factor",
        name="Suply Fan",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="fan_sup_factor",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
):
    sensor_name = entry.data.get(CONF_NAME)
    coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AAtreaDeviceSensor] = [
        AAtreaDeviceSensor(coordinator, description, sensor_name)
        for description in ATREA_SENSORS
    ]
    async_add_entities(entities, update_before_add=True)


class AAtreaDeviceSensor(
    CoordinatorEntity[AmotionAtreaCoordinator], SensorEntity
):

    entity_description: AtreaSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description: AtreaSensorEntityDescription,
        sensor_name
    ) -> None:
        super().__init__(coordinator)
        self._atrea = coordinator.aatrea
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = "%s-%s" % (sensor_name, f"amotionatrea_{description.key}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._atrea.name)},
            manufacturer=self._atrea.brand,
            model=self._atrea.model,
            name=self._atrea.name,
            sw_version=self._atrea.sw_version,
            serial_number=self._atrea.serial,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._atrea.status[self.entity_description.json_value]

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()
