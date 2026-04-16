"""Tests for Amotion Atrea integration init module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from custom_components.amotionatrea import (
    AmotionAtrea,
    AmotionAtreaCoordinator,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.amotionatrea.const import DOMAIN, TIMEOUT


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    # Mock async_create_background_task to avoid RuntimeWarning by scheduling the coroutine
    hass.async_create_background_task = MagicMock(side_effect=lambda coro, *args, **kwargs: asyncio.create_task(coro))
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "url": "ws://192.168.1.100:8080/",
        "username": "test_user",
        "password": "test_password",
    }
    return entry


class TestAmotionAtrea:
    """Test cases for AmotionAtrea class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_hass):
        """Test AmotionAtrea initialization."""
        atrea = AmotionAtrea(
            mock_hass,
            "ws://192.168.1.100:8080/",
            "test_user",
            "test_password"
        )
        
        assert atrea._url == "ws://192.168.1.100:8080/"
        assert atrea._username == "test_user"
        assert atrea._password == "test_password"
        assert atrea.logged_in is False
        assert atrea._msg_id == 0
        assert atrea._messages == {}
        assert atrea._max_flow is None
        assert atrea.has_uv_lamp is False
        assert atrea.brand == "Atrea"
        assert atrea.name == "Atrea"
        # Check status dict has all expected keys
        assert 'current_temperature' in atrea.status
        assert 'setpoint' in atrea.status

    @pytest.mark.asyncio
    async def test_send_increments_msg_id(self, mock_hass):
        """Test that send increments message ID."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            # Mock the websocket connection
            atrea._websocket = mock_ws_instance
            
            # Call send
            msg_id = await atrea.send('{"endpoint": "test", "args": null}')
            
            assert msg_id == 1
            assert atrea._msg_id == 1
            
            # Send another message
            msg_id2 = await atrea.send('{"endpoint": "test2", "args": null}')
            assert msg_id2 == 2
            assert atrea._msg_id == 2

    @pytest.mark.asyncio
    async def test_send_timeout_raises_config_entry_not_ready(self, mock_hass):
        """Test that send timeout raises ConfigEntryNotReady."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(side_effect=TimeoutError())
            MockWS.return_value = mock_ws_instance
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            atrea._websocket = mock_ws_instance
            
            with pytest.raises(ConfigEntryNotReady):
                await atrea.send('{"endpoint": "test", "args": null}')

    @pytest.mark.asyncio
    async def test_update_returns_message(self, mock_hass):
        """Test update method returns message."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            MockWS.return_value = AsyncMock()
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            # Add a message to _messages
            atrea._messages[5] = {"test": "data"}
            
            result = await atrea.update(5)
            
            assert result == {"test": "data"}
            assert 5 not in atrea._messages

    @pytest.mark.asyncio
    async def test_update_timeout(self, mock_hass):
        """Test update method times out."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            MockWS.return_value = AsyncMock()
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            # Mock asyncio.sleep to speed up test
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await atrea.update(999)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_receive_stores_message(self, mock_hass):
        """Test receive method stores message."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            MockWS.return_value = AsyncMock()
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            message = {
                'id': 5,
                'code': 'OK',
                'response': {'test': 'data'},
                'type': 'response'
            }
            
            await atrea.receive(message)
            
            assert 5 in atrea._messages
            assert atrea._messages[5] == {'test': 'data'}

    @pytest.mark.asyncio
    async def test_receive_unauthorized_raises_error(self, mock_hass):
        """Test receive method raises ConfigEntryNotReady on UNAUTHORIZED."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            MockWS.return_value = AsyncMock()
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            message = {
                'id': 5,
                'code': 'UNAUTHORIZED',
                'response': None,
                'type': 'response'
            }
            
            with pytest.raises(ConfigEntryNotReady):
                await atrea.receive(message)

    @pytest.mark.asyncio
    async def test_receive_ui_info_event_updates_status(self, mock_hass):
        """Test receive method updates status on ui_info event."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            MockWS.return_value = AsyncMock()
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            # Set logged_in to True
            atrea.logged_in = True
            
            message = {
                'type': 'event',
                'event': 'ui_info',
                'args': {
                    'unit': {
                        'temp_sup': 22.5,
                        'temp_oda': 15.0,
                        'temp_ida': 23.0,
                        'temp_eha': 20.0,
                        'temp_eta': 21.0,
                        'season_current': 'HEATING',
                        'fan_eta_factor': 60,
                        'fan_sup_factor': 60,
                    },
                    'requests': {
                        'temp_request': 21.0,
                        'fan_power_req': 50,
                    }
                }
            }
            
            await atrea.receive(message)
            
            assert atrea.status['current_temperature'] == 22.5
            assert atrea.status['setpoint'] == 21.0
            assert atrea.status['season_current'] == 'HEATING'

    @pytest.mark.asyncio
    async def test_set_temperature(self, mock_hass):
        """Test set_temperature method."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            atrea._websocket = mock_ws_instance
            atrea.logged_in = True
            
            # Mock update to return immediately
            with patch.object(atrea, 'update', new_callable=AsyncMock, return_value=None):
                await atrea.set_temperature(22.0)
            
            # Verify send was called with correct message
            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_fan_mode_with_max_flow(self, mock_hass):
        """Test set_fan_mode when max_flow is set."""
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            atrea._websocket = mock_ws_instance
            atrea._max_flow = 100
            atrea._min_flow = 10
            atrea.logged_in = True
            
            with patch.object(atrea, 'update', new_callable=AsyncMock, return_value=None):
                await atrea.set_fan_mode(50)
            
            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_hvac_mode_heat_cool(self, mock_hass):
        """Test set_hvac_mode with HEAT_COOL."""
        from homeassistant.components.climate import HVACMode
        
        with patch('custom_components.amotionatrea.AtreaWebsocket') as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance
            
            atrea = AmotionAtrea(
                mock_hass,
                "ws://192.168.1.100:8080/",
                "test_user",
                "test_password"
            )
            
            atrea._websocket = mock_ws_instance
            atrea.logged_in = True
            
            with patch.object(atrea, 'update', new_callable=AsyncMock, return_value=None):
                await atrea.set_hvac_mode(HVACMode.HEAT_COOL)
            
            assert mock_ws_instance.send.called


@pytest.mark.skip(reason="DataUpdateCoordinator requires frame helper in test environment")
class TestAmotionAtreaCoordinator:
    """Test cases for AmotionAtreaCoordinator class."""

    def test_coordinator_initialization(self, mock_hass):
        """Test coordinator initialization."""
        # Create a mock atrea object instead of real instance
        mock_atrea = MagicMock()
        
        coordinator = AmotionAtreaCoordinator(mock_hass, mock_atrea)
        
        assert coordinator.aatrea == mock_atrea
        assert coordinator.update_interval == timedelta(seconds=30)
        assert coordinator.always_update is True

    @pytest.mark.asyncio
    async def test_async_update_data_success(self, mock_hass):
        """Test successful data update."""
        # Create a mock atrea object instead of real instance
        mock_atrea = MagicMock()
        mock_atrea.fetch = AsyncMock(return_value={'data': 'test'})
        
        coordinator = AmotionAtreaCoordinator(mock_hass, mock_atrea)
        
        result = await coordinator._async_update_data()
        
        assert result == {'data': 'test'}

    @pytest.mark.asyncio
    async def test_async_update_data_failure(self, mock_hass):
        """Test data update failure raises UpdateFailed."""
        # Create a mock atrea object instead of real instance
        mock_atrea = MagicMock()
        mock_atrea.fetch = AsyncMock(side_effect=Exception("API error"))
        
        coordinator = AmotionAtreaCoordinator(mock_hass, mock_atrea)
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

class TestAsyncSetupEntry:
    """Test cases for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry):
        """Test successful setup entry."""
        with patch('custom_components.amotionatrea.AmotionAtrea') as MockAmotionAtrea:
            mock_atrea = MagicMock()
            MockAmotionAtrea.return_value = mock_atrea
            
            with patch('custom_components.amotionatrea.AmotionAtreaCoordinator') as MockCoordinator:
                mock_coordinator = MagicMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                MockCoordinator.return_value = mock_coordinator
                
                mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
                
                result = await async_setup_entry(mock_hass, mock_config_entry)
                
                assert result is True
                assert DOMAIN in mock_hass.data
                assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_async_setup_entry_failure(self, mock_hass, mock_config_entry):
        """Test setup entry failure raises ConfigEntryNotReady."""
        with patch('custom_components.amotionatrea.AmotionAtrea', side_effect=Exception("Setup failed")):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(mock_hass, mock_config_entry)


class TestAsyncUnloadEntry:
    """Test cases for async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_hass, mock_config_entry):
        """Test unload entry."""
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        
        result = await async_unload_entry(mock_hass, mock_config_entry)
        
        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()
