"""Support for Amotion Atrea sensors."""

import logging
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

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


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
        translation_key="exhaust_temperature",
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
        name="Current Season",
        icon="mdi:sun-snowflake-variant",
        device_class=SensorDeviceClass.ENUM,
        options=["NON_HEATING", "HEATING"],
        json_value="season_current",
    ),
    AtreaSensorEntityDescription(
        key="fan_sup_factor",
        name="Supply Fan",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="fan_sup_factor",
    ),

    # Additional sensors from ui_diagram_data
    AtreaSensorEntityDescription(
        key="bypass_estim",
        translation_key="bypass_estim",
        name="Bypass Estimation",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="bypass_estim",
    ),
    AtreaSensorEntityDescription(
        key="preheater_factor",
        translation_key="preheater_factor",
        name="Preheater Factor",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        json_value="preheater_factor",
    ),

    # New sensors for maintenance data
    AtreaSensorEntityDescription(
        key="filters_last_change",
        translation_key="filters_last_change",
        name="Filters Last Change",
        icon="mdi:filter",
        json_value="filters_last_change",
    ),
    AtreaSensorEntityDescription(
        key="inspection_date",
        translation_key="inspection_date",
        name="Inspection Date",
        icon="mdi:calendar-clock",
        json_value="inspection_date",
    ),
    AtreaSensorEntityDescription(
        key="motor1_hours",
        translation_key="motor1_hours",
        name="Motor 1 Operating Hours",
        icon="mdi:motorbike",
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL,
        json_value="motor1_hours",
    ),
    AtreaSensorEntityDescription(
        key="motor2_hours",
        translation_key="motor2_hours",
        name="Motor 2 Operating Hours",
        icon="mdi:motorbike",
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL,
        json_value="motor2_hours",
    ),
    AtreaSensorEntityDescription(
        key="uv_lamp_hours",
        translation_key="uv_lamp_hours",
        name="UV Lamp Operating Hours",
        icon="mdi:lightbulb-outline",
        native_unit_of_measurement="h",
        state_class=SensorStateClass.TOTAL,
        json_value="uv_lamp_hours",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
):
    sensor_name = entry.data.get(CONF_NAME)
    coordinator: AmotionAtreaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AAtreaDeviceSensor] = []
    for description in ATREA_SENSORS:
        if description.json_value == "uv_lamp_hours" and not coordinator.aatrea.has_uv_lamp:
            continue
        entities.append(AAtreaDeviceSensor(coordinator, description, sensor_name))
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
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        value = self._atrea.status.get(self.entity_description.json_value)
        if not value:
            return None

        # Handle date formatting for filters_last_change and inspection_date
        if self.entity_description.json_value in ["filters_last_change", "inspection_date"]:
            day = value.get("day")
            month = value.get("month")
            year = value.get("year")
            if day is not None and month is not None and year is not None:
                return f"{year}-{month:02d}-{day:02d}"
            return None

        # Return numerical values as they are
        return value

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()

