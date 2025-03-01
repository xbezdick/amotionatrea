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

