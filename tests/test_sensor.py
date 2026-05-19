"""Tests for Amotion Atrea sensor module."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from custom_components.amotionatrea.sensor import (
    AAtreaDeviceSensor,
    AtreaSensorEntityDescription,
    ATREA_SENSORS,
    async_setup_entry,
)
from custom_components.amotionatrea.const import DOMAIN


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "url": "ws://192.168.1.100:8080/",
        "username": "test_user",
        "password": "test_password",
        "name": "Test Atrea"
    }
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.aatrea = MagicMock()
    coordinator.aatrea.name = "Test Atrea"
    coordinator.aatrea.brand = "Atrea"
    coordinator.aatrea.model = "DUPLEX 380 ECV5.aM-CL"
    coordinator.aatrea.sw_version = "ATC-v2.3.0"
    coordinator.aatrea.serial = "12345678"
    coordinator.aatrea.status = {
        'temp_oda': 15.0,
        'temp_ida': 23.0,
        'temp_eha': 20.0,
        'fan_eta_factor': 60,
        'temp_sup': 22.5,
        'temp_eta': 21.0,
        'season_current': 'HEATING',
        'fan_sup_factor': 55,
        'bypass_estim': 30,
        'preheater_factor': 20,
        'filters_last_change': {'day': 15, 'month': 6, 'year': 2023},
        'inspection_date': {'day': 1, 'month': 12, 'year': 2023},
        'motor1_hours': 7200,
        'motor2_hours': 7150,
        'uv_lamp_hours': 3600,
    }
    coordinator.aatrea.has_uv_lamp = True
    return coordinator


class TestAtreaSensorEntityDescription:
    """Test cases for AtreaSensorEntityDescription dataclass."""

    def test_sensor_description_creation(self):
        """Test creating a sensor description."""
        desc = AtreaSensorEntityDescription(
            key="test_sensor",
            translation_key="test",
            name="Test Sensor",
            json_value="test_value"
        )

        assert desc.key == "test_sensor"
        assert desc.translation_key == "test"
        assert desc.name == "Test Sensor"
        assert desc.json_value == "test_value"


class TestATREA_SENSORS:
    """Test cases for ATREA_SENSORS tuple."""

    def test_sensors_tuple_not_empty(self):
        """Test that ATREA_SENSORS is not empty."""
        assert len(ATREA_SENSORS) > 0

    def test_all_sensors_have_required_fields(self):
        """Test that all sensors have required fields."""
        for sensor in ATREA_SENSORS:
            assert sensor.key is not None
            assert sensor.name is not None
            assert sensor.json_value is not None


class TestAAtreaDeviceSensor:
    """Test cases for AAtreaDeviceSensor class."""

    def test_initialization(self, mock_coordinator):
        """Test sensor initialization."""
        description = ATREA_SENSORS[0]
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.name == description.name
        assert sensor._attr_unique_id == f"Test Atrea-amotionatrea_{description.key}"

    def test_native_value_numeric(self, mock_coordinator):
        """Test native_value for numeric sensors."""
        description = AtreaSensorEntityDescription(
            key="test_temp",
            name="Test Temperature",
            json_value="temp_oda"
        )
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.native_value == 15.0

    def test_native_value_none(self, mock_coordinator):
        """Test native_value when value is None."""
        # Set a value to None in status
        mock_coordinator.aatrea.status['test_null'] = None

        description = AtreaSensorEntityDescription(
            key="test_null",
            name="Test Null",
            json_value="test_null"
        )
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.native_value is None

    def test_native_value_date_formatting(self, mock_coordinator):
        """Test native_value for date sensors."""
        description = AtreaSensorEntityDescription(
            key="filters_last_change",
            name="Filters Last Change",
            json_value="filters_last_change"
        )
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.native_value == "2023-06-15"

    def test_native_value_inspection_date(self, mock_coordinator):
        """Test native_value for inspection date."""
        description = AtreaSensorEntityDescription(
            key="inspection_date",
            name="Inspection Date",
            json_value="inspection_date"
        )
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.native_value == "2023-12-01"

    def test_native_value_motor_hours(self, mock_coordinator):
        """Test native_value for motor hours."""
        description = AtreaSensorEntityDescription(
            key="motor1_hours",
            name="Motor 1 Operating Hours",
            json_value="motor1_hours"
        )
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        assert sensor.native_value == 7200

    def test_device_info(self, mock_coordinator):
        """Test device_info property."""
        description = ATREA_SENSORS[0]
        sensor = AAtreaDeviceSensor(mock_coordinator, description, "Test Atrea")

        device_info = sensor.device_info

        assert device_info['identifiers'] == {(DOMAIN, "Test Atrea")}
        assert device_info['manufacturer'] == "Atrea"
        assert device_info['model'] == "DUPLEX 380 ECV5.aM-CL"
        assert device_info['name'] == "Test Atrea"

    def test_uv_lamp_sensor_skipped_when_no_uv_lamp(self, mock_coordinator):
        """Test that UV lamp sensor is skipped when no UV lamp."""
        mock_coordinator.aatrea.has_uv_lamp = False

        uv_sensor_desc = None
        for desc in ATREA_SENSORS:
            if desc.key == "uv_lamp_hours":
                uv_sensor_desc = desc
                break

        assert uv_sensor_desc is not None
        # When has_uv_lamp is False, the sensor should not be created
        # This is tested in async_setup_entry


@pytest.mark.asyncio
class TestAsyncSetupEntrySensor:
    """Test cases for async_setup_entry in sensor module."""

    async def test_async_setup_entry_creates_all_sensors(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test sensor setup entry creates all sensors."""
        # Setup hass data
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

        # Mock async_add_entities
        async_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Verify entities were added
        assert async_add_entities.called
        entities = async_add_entities.call_args[0][0]

        # Should create all sensors except UV lamp if not present
        # Count expected sensors
        expected_count = len([s for s in ATREA_SENSORS if not (s.key == "uv_lamp_hours" and not mock_coordinator.aatrea.has_uv_lamp)])
        assert len(entities) == expected_count

    async def test_async_setup_entry_skips_uv_lamp_when_not_present(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test that UV lamp sensor is skipped when not present."""
        mock_coordinator.aatrea.has_uv_lamp = False
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

        async_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        entities = async_add_entities.call_args[0][0]

        # Verify no UV lamp sensor
        for entity in entities:
            assert entity.entity_description.key != "uv_lamp_hours"

"""Extended tests for Amotion Atrea sensor module."""

import pytest
from custom_components.amotionatrea.sensor import AAtreaDeviceSensor, AtreaSensorEntityDescription


class TestSensorExtended:
    """Extended test cases for sensor module."""

    @pytest.mark.asyncio
    async def test_native_value_partial_date(self):
        """Test native_value with partial date data."""
        mock_coordinator = type('MockCoordinator', (), {'aatrea': type('MockAtrea', (), {
            'name': "TestDevice",
            'brand': "Atrea",
            'model': "DUPLEX 380",
            'sw_version': "v1.0",
            'serial': "ABC123",
            # Only day and month, missing year
            'status': {'filters_last_change': {'day': 15, 'month': 6}}
        })()})()

        description = AtreaSensorEntityDescription(
            key="filters_last_change",
            translation_key="filters_last_change",
            json_value="filters_last_change",
        )

        sensor = AAtreaDeviceSensor(mock_coordinator, description, "sensor_name")

        # Should return None when date is incomplete
        assert sensor.native_value is None

    @pytest.mark.asyncio
    async def test_native_value_complete_date(self):
        """Test native_value with complete date data."""
        mock_coordinator = type('MockCoordinator', (), {'aatrea': type('MockAtrea', (), {
            'name': "TestDevice",
            'brand': "Atrea",
            'model': "DUPLEX 380",
            'sw_version': "v1.0",
            'serial': "ABC123",
            'status': {'filters_last_change': {'day': 15, 'month': 6, 'year': 2024}}
        })()})()

        description = AtreaSensorEntityDescription(
            key="filters_last_change",
            translation_key="filters_last_change",
            json_value="filters_last_change",
        )

        sensor = AAtreaDeviceSensor(mock_coordinator, description, "sensor_name")

        assert sensor.native_value == "2024-06-15"

    @pytest.mark.asyncio
    async def test_native_value_numeric_zero(self):
        """Test native_value with zero value."""
        mock_coordinator = type('MockCoordinator', (), {'aatrea': type('MockAtrea', (), {
            'name': "TestDevice",
            'brand': "Atrea",
            'model': "DUPLEX 380",
            'sw_version': "v1.0",
            'serial': "ABC123",
            'status': {'bypass_estim': 0}
        })()})()

        description = AtreaSensorEntityDescription(
            key="bypass_estim",
            translation_key="bypass_estim",
            json_value="bypass_estim",
        )

        sensor = AAtreaDeviceSensor(mock_coordinator, description, "sensor_name")

        # Zero should be returned, not None
        assert sensor.native_value == 0

    @pytest.mark.asyncio
    async def test_async_update(self):
        """Test async_update method."""
        from unittest.mock import AsyncMock

        mock_coordinator = type('MockCoordinator', (), {
            'aatrea': type('MockAtrea', (), {
                'name': "TestDevice",
                'brand': "Atrea",
                'model': "DUPLEX 380",
                'sw_version': "v1.0",
                'serial': "ABC123",
            })(),
            'async_request_refresh': AsyncMock()
        })()

        description = AtreaSensorEntityDescription(
            key="outside_temperature",
            translation_key="outside_temperature",
            json_value="temp_oda",
        )

        sensor = AAtreaDeviceSensor(mock_coordinator, description, "sensor_name")

        await sensor.async_update()

        mock_coordinator.async_request_refresh.assert_called_once()
