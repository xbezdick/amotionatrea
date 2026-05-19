"""Tests for Amotion Atrea climate module."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import HVACAction
from custom_components.amotionatrea.climate import AAtreaDevice, async_setup_entry
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
        'current_temperature': 22.5,
        'setpoint': 21.0,
        'season_current': 'HEATING',
        'fan_mode': 50,
        'temp_oda': 15.0,
        'temp_ida': 23.0,
        'temp_eha': 20.0,
        'temp_eta': 21.0,
        'temp_sup': 22.5,
    }
    return coordinator


class TestAAtreaDevice:
    """Test cases for AAtreaDevice class."""

    def test_initialization(self, mock_coordinator):
        """Test device initialization."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.name == "Test Atrea"
        assert device._attr_unique_id == "Test Atrea-Test Atrea"
        assert device.temperature_unit == "°C"

    def test_temperature_unit(self, mock_coordinator):
        """Test temperature unit property."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.temperature_unit == "°C"

    def test_hvac_mode_heating(self, mock_coordinator):
        """Test hvac_mode when in heating season."""
        mock_coordinator.aatrea.status['season_current'] = 'HEATING'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_non_heating(self, mock_coordinator):
        """Test hvac_mode when in non-heating season."""
        mock_coordinator.aatrea.status['season_current'] = 'NON_HEATING'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_mode == HVACMode.COOL

    def test_hvac_mode_auto(self, mock_coordinator):
        """Test hvac_mode when in auto mode."""
        mock_coordinator.aatrea.status['season_current'] = 'auto'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_mode == HVACMode.AUTO

    def test_hvac_mode_off(self, mock_coordinator):
        """Test hvac_mode when unknown."""
        mock_coordinator.aatrea.status['season_current'] = 'UNKNOWN'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_mode == HVACMode.OFF

    def test_hvac_action_heating(self, mock_coordinator):
        """Test hvac_action when heating."""
        mock_coordinator.aatrea.status['season_current'] = 'HEATING'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_action == HVACAction.HEATING

    def test_hvac_action_cooling(self, mock_coordinator):
        """Test hvac_action when cooling."""
        mock_coordinator.aatrea.status['season_current'] = 'NON_HEATING'
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_action == HVACAction.COOLING

    def test_hvac_modes(self, mock_coordinator):
        """Test hvac_modes property."""
        from custom_components.amotionatrea.const import HVAC_MODES
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.hvac_modes == HVAC_MODES

    def test_current_temperature(self, mock_coordinator):
        """Test current_temperature property."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.current_temperature == 22.5

    def test_target_temperature(self, mock_coordinator):
        """Test target_temperature property."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.target_temperature == 21.0

    @pytest.mark.asyncio
    async def test_async_set_temperature(self, mock_coordinator):
        """Test async_set_temperature method."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        # Mock the atrea set_temperature method
        mock_coordinator.aatrea.set_temperature = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        
        await device.async_set_temperature(temperature=23.0)
        
        mock_coordinator.aatrea.set_temperature.assert_called_once_with(23)
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_set_hvac_mode(self, mock_coordinator):
        """Test async_set_hvac_mode method."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        # Mock the atrea set_hvac_mode method
        mock_coordinator.aatrea.set_hvac_mode = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        
        await device.async_set_hvac_mode(HVACMode.HEAT)
        
        mock_coordinator.aatrea.set_hvac_mode.assert_called_once_with(HVACMode.HEAT)
        mock_coordinator.async_request_refresh.assert_called_once()

    def test_fan_mode(self, mock_coordinator):
        """Test fan_mode property."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        # Test rounding to nearest 5
        mock_coordinator.aatrea.status['fan_mode'] = 47
        assert device.fan_mode == "45"
        
        mock_coordinator.aatrea.status['fan_mode'] = 48
        assert device.fan_mode == "50"

    def test_fan_modes(self, mock_coordinator):
        """Test fan_modes property."""
        from custom_components.amotionatrea.const import DEFAULT_FAN_MODE_LIST
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        assert device.fan_modes == DEFAULT_FAN_MODE_LIST

    @pytest.mark.asyncio
    async def test_async_set_fan_mode(self, mock_coordinator):
        """Test async_set_fan_mode method."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        # Mock the atrea set_fan_mode method
        mock_coordinator.aatrea.set_fan_mode = AsyncMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        
        await device.async_set_fan_mode("50")
        
        mock_coordinator.aatrea.set_fan_mode.assert_called_once_with("50")
        mock_coordinator.async_request_refresh.assert_called_once()

    def test_device_info(self, mock_coordinator):
        """Test device_info property."""
        device = AAtreaDevice(mock_coordinator, "Test Atrea")
        
        device_info = device.device_info
        
        assert device_info['identifiers'] == {(DOMAIN, "Test Atrea")}
        assert device_info['manufacturer'] == "Atrea"
        assert device_info['model'] == "DUPLEX 380 ECV5.aM-CL"
        assert device_info['name'] == "Test Atrea"
        assert device_info['sw_version'] == "ATC-v2.3.0"
        assert device_info['serial_number'] == "12345678"


class TestAsyncSetupEntryClimate:
    """Test cases for async_setup_entry in climate module."""

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test climate setup entry."""
        # Setup hass data
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}
        
        # Mock async_add_entities
        async_add_entities = MagicMock()
        
        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)
        
        # Verify entities were added
        assert async_add_entities.called
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], AAtreaDevice)

"""Extended tests for Amotion Atrea climate module."""

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import HVACAction
from custom_components.amotionatrea.climate import AAtreaDevice
