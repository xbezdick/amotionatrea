"""Support for Amotion Atrea sensors."""
import time
import logging
import requests, websockets
import json

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
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
        name="Outside Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_oda",
    ),
    AtreaSensorEntityDescription(
        key="inside_temperature",
        translation_key="inside_temperature",
        name="Inside Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="temp_ida",
    ),
    AtreaSensorEntityDescription(
        key="exhaust_temperature",
        translation_key="exaust_temperature",
        name="Exhaust Temperature",
        icon="mdi:thermometer",
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
    if sensor_name is None:
        sensor_name = "aatrea"

    coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AAtreaDeviceSensor] = [
        AAtreaDeviceSensor(coordinator, entry, description, sensor_name)
        for description in ATREA_SENSORS
    ]
    async_add_entities(entities)


class AAtreaDeviceSensor(
    CoordinatorEntity[AmotionAtreaCoordinator], SensorEntity
):

    entity_description: AtreaSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry,
        description: AtreaSensorEntityDescription,
        sensor_name,
    ) -> None:
        super().__init__(coordinator)
        self._atrea = coordinator.aatrea
        self.entity_description = description
        self._name = sensor_name
        self._attr_unique_id = "%s-%s-%s" % (sensor_name, entry.data.get(CONF_HOST), description.key)
        self._device_unique_id = "%s-%s" % (sensor_name, entry.data.get(CONF_HOST))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_unique_id)},
            manufacturer="Atrea",
            model="TODOFIXME",
            name=self._name,
            sw_version="FIXME",
        )
        self.updatePending = False

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        LOGGER.debug("CALLED %s" % self._name)
        return self._atrea.status[self.entity_description.json_value]
