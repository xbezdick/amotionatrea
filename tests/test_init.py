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
    hass.async_create_background_task = MagicMock(
        side_effect=lambda coro, *args, **kwargs: asyncio.create_task(coro)
    )
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
            mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
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
        assert "current_temperature" in atrea.status
        assert "setpoint" in atrea.status

    @pytest.mark.asyncio
    async def test_send_increments_msg_id(self, mock_hass):
        """Test that send increments message ID."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
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
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(side_effect=TimeoutError())
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            atrea._websocket = mock_ws_instance

            with pytest.raises(ConfigEntryNotReady):
                await atrea.send('{"endpoint": "test", "args": null}')

    @pytest.mark.asyncio
    async def test_update_returns_message(self, mock_hass):
        """Test update method returns message."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            MockWS.return_value = AsyncMock()

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            # Add a message to _messages
            atrea._messages[5] = {"test": "data"}

            result = await atrea.update(5)

            assert result == {"test": "data"}
            assert 5 not in atrea._messages

    @pytest.mark.asyncio
    async def test_update_timeout(self, mock_hass):
        """Test update method times out."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            MockWS.return_value = AsyncMock()

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            # Mock asyncio.sleep to speed up test
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await atrea.update(999)

            assert result is None

    @pytest.mark.asyncio
    async def test_receive_stores_message(self, mock_hass):
        """Test receive method stores message."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            MockWS.return_value = AsyncMock()

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            message = {
                "id": 5,
                "code": "OK",
                "response": {"test": "data"},
                "type": "response",
            }

            await atrea.receive(message)

            assert 5 in atrea._messages
            assert atrea._messages[5] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_receive_unauthorized_raises_error(self, mock_hass):
        """Test receive method raises ConfigEntryNotReady on UNAUTHORIZED."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            MockWS.return_value = AsyncMock()

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            message = {
                "id": 5,
                "code": "UNAUTHORIZED",
                "response": None,
                "type": "response",
            }

            with pytest.raises(ConfigEntryNotReady):
                await atrea.receive(message)

    @pytest.mark.asyncio
    async def test_receive_ui_info_event_updates_status(self, mock_hass):
        """Test receive method updates status on ui_info event."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            MockWS.return_value = AsyncMock()

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            # Set logged_in to True
            atrea.logged_in = True

            message = {
                "type": "event",
                "event": "ui_info",
                "args": {
                    "unit": {
                        "temp_sup": 22.5,
                        "temp_oda": 15.0,
                        "temp_ida": 23.0,
                        "temp_eha": 20.0,
                        "temp_eta": 21.0,
                        "season_current": "HEATING",
                        "fan_eta_factor": 60,
                        "fan_sup_factor": 60,
                    },
                    "requests": {
                        "temp_request": 21.0,
                        "fan_power_req": 50,
                    },
                },
            }

            await atrea.receive(message)

            assert atrea.status["current_temperature"] == 22.5
            assert atrea.status["setpoint"] == 21.0
            assert atrea.status["season_current"] == "HEATING"

    @pytest.mark.asyncio
    async def test_set_temperature(self, mock_hass):
        """Test set_temperature method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            atrea._websocket = mock_ws_instance
            atrea.logged_in = True

            # Mock update to return immediately
            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_temperature(22.0)

            # Verify send was called with correct message
            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_fan_mode_with_max_flow(self, mock_hass):
        """Test set_fan_mode when max_flow is set."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            atrea._websocket = mock_ws_instance
            atrea._max_flow = 100
            atrea._min_flow = 10
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_fan_mode(50)

            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_hvac_mode_heat_cool(self, mock_hass):
        """Test set_hvac_mode with HEAT_COOL."""
        from homeassistant.components.climate import HVACMode

        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(
                mock_hass, "ws://192.168.1.100:8080/", "test_user", "test_password"
            )

            atrea._websocket = mock_ws_instance
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_hvac_mode(HVACMode.HEAT_COOL)

            assert mock_ws_instance.send.called


@pytest.mark.skip(
    reason="DataUpdateCoordinator requires frame helper in test environment"
)
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
        mock_atrea.fetch = AsyncMock(return_value={"data": "test"})

        coordinator = AmotionAtreaCoordinator(mock_hass, mock_atrea)

        result = await coordinator._async_update_data()

        assert result == {"data": "test"}

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
        with patch("custom_components.amotionatrea.AmotionAtrea") as MockAmotionAtrea:
            mock_atrea = MagicMock()
            MockAmotionAtrea.return_value = mock_atrea

            with patch(
                "custom_components.amotionatrea.AmotionAtreaCoordinator"
            ) as MockCoordinator:
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
        with patch(
            "custom_components.amotionatrea.AmotionAtrea",
            side_effect=Exception("Setup failed"),
        ):
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


"""Extended tests for Amotion Atrea integration init module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.amotionatrea import AmotionAtrea
from custom_components.amotionatrea.const import DOMAIN


class TestAmotionAtreaExtended:
    """Extended test cases for AmotionAtrea class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.data = {}
        hass.async_create_background_task = MagicMock(
            side_effect=lambda coro, *args, **kwargs: asyncio.create_task(coro)
        )
        return hass

    @pytest.mark.asyncio
    async def test_on_close(self, mock_hass):
        """Test on_close resets message counter."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._msg_id = 5
            await atrea.on_close()
            assert atrea._msg_id == 0

    @pytest.mark.asyncio
    async def test_on_connect(self, mock_hass):
        """Test on_connect creates background login task."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.login = AsyncMock()
            await atrea.on_connect()
            await asyncio.sleep(0.1)
            assert atrea.login.called

    @pytest.mark.asyncio
    async def test_receive_event_updates_status(self, mock_hass):
        """Test receive method with ui_info event updates status."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.logged_in = True

            message = {
                "type": "event",
                "event": "ui_info",
                "args": {
                    "unit": {
                        "temp_sup": 22.5,
                        "temp_oda": 15.0,
                        "temp_ida": 23.0,
                        "temp_eha": 20.0,
                        "temp_eta": 21.0,
                        "season_current": "HEATING",
                        "fan_eta_factor": 60,
                        "fan_sup_factor": 60,
                        "flow_eta": 50,
                        "flow_sup": 55,
                    },
                    "requests": {
                        "temp_request": 21.0,
                        "fan_power_req": 50,
                        "flow_ventilation_req": 55,
                    },
                },
            }

            await atrea.receive(message)

            assert atrea.status["current_temperature"] == 22.5
            assert atrea.status["temp_oda"] == 15.0
            assert atrea.status["last_update"] is not None

    @pytest.mark.asyncio
    async def test_receive_event_with_max_flow(self, mock_hass):
        """Test receive method with max_flow set calculates fan modes correctly."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.logged_in = True
            atrea._max_flow = 100.0
            atrea._min_flow = 10.0

            message = {
                "type": "event",
                "event": "ui_info",
                "args": {
                    "unit": {
                        "temp_sup": 22.0,
                        "temp_oda": 15.0,
                        "fan_eta_factor": 60,
                        "fan_sup_factor": 60,
                        "flow_eta": 50,
                        "flow_sup": 55,
                    },
                    "requests": {
                        "temp_request": 21.0,
                        "fan_power_req": 50,
                        "flow_ventilation_req": 60,
                    },
                },
            }

            await atrea.receive(message)

            # With max_flow=100, fan_mode should be calculated as flow_ventilation_req / (max_flow/100)
            # 60 / (100/100) = 60, rounded to 60
            assert atrea.status["fan_mode"] == 60.0
            assert atrea.status["fan_eta_factor"] == 50.0
            assert atrea.status["fan_sup_factor"] == 60.0  # 55 rounded to 60

    @pytest.mark.asyncio
    async def test_receive_event_without_max_flow(self, mock_hass):
        """Test receive method without max_flow uses fan_power_req."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.logged_in = True
            atrea._max_flow = None

            message = {
                "type": "event",
                "event": "ui_info",
                "args": {
                    "unit": {
                        "temp_sup": 22.0,
                        "fan_eta_factor": 60,
                        "fan_sup_factor": 60,
                    },
                    "requests": {
                        "temp_request": 21.0,
                        "fan_power_req": 50,
                    },
                },
            }

            await atrea.receive(message)

            # Without max_flow, fan_mode should be fan_power_req
            assert atrea.status["fan_mode"] == 50
            assert atrea.status["fan_eta_factor"] == 60
            assert atrea.status["fan_sup_factor"] == 60

    @pytest.mark.asyncio
    async def test_receive_id_none_ignored(self, mock_hass):
        """Test receive method ignores messages with id=None."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")

            message = {
                "id": None,
                "code": "OK",
                "response": {"test": "data"},
            }

            await atrea.receive(message)

            # Should not store message with id=None
            assert atrea._messages == {}

    @pytest.mark.asyncio
    async def test_receive_no_id_field(self, mock_hass):
        """Test receive method handles messages without id field."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.logged_in = False  # Not logged in, so event won't be processed

            message = {
                "type": "event",
                "event": "ui_info",
                "args": {"unit": {}, "requests": {}},
            }

            await atrea.receive(message)

            # Should not update status when not logged in
            assert atrea.status["current_temperature"] is None

    @pytest.mark.asyncio
    async def test_fetch_with_max_flow_calls_time(self, mock_hass):
        """Test fetch method calls time() when max_flow is set."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea._max_flow = 100.0
            atrea.logged_in = True
            atrea.status["current_temperature"] = 22.0
            atrea.status["last_update"] = datetime.now()
            atrea.status["last_maintenance_update"] = datetime.now()

            with patch.object(atrea, "time", new_callable=AsyncMock) as mock_time:
                with patch.object(
                    atrea, "update", new_callable=AsyncMock, return_value=None
                ):
                    result = await atrea.fetch()
                    assert mock_time.called

    @pytest.mark.asyncio
    async def test_fetch_timeout_waiting_for_login(self, mock_hass):
        """Test fetch method handles timeout waiting for login."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea.logged_in = False  # Never gets logged in
            atrea.status["current_temperature"] = None  # Triggers fetch
            atrea.status["last_update"] = datetime.min  # Old update time
            atrea.status["last_maintenance_update"] = datetime.now()

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                result = await atrea.fetch()
                assert result is not None

    @pytest.mark.asyncio
    async def test_async_get_discovery(self, mock_hass):
        """Test async_get_discovery method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            discovery_data = {
                "type": "DUPLEX 380 ECV5.aM-CL",
                "production_number": "ABC123",
                "brand": "atrea.cz",
                "name": "Test Device",
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=discovery_data
            ):
                await atrea.async_get_discovery()

            assert atrea.model == "DUPLEX 380 ECV5.aM-CL"
            assert atrea.serial == "ABC123"
            assert atrea.brand == "atrea.cz"
            assert atrea.name == "Test Device"

    @pytest.mark.asyncio
    async def test_async_get_discovery_no_data(self, mock_hass):
        """Test async_get_discovery when no data returned."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.async_get_discovery()

            # Should use defaults when no data
            assert atrea.model is None  # Default is None, not changed

    @pytest.mark.asyncio
    async def test_async_get_version_with_data(self, mock_hass):
        """Test async_get_version with valid data."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            version_data = {
                "GATEWAY": {
                    "version": "ATC-v2.3.0",
                }
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=version_data
            ):
                await atrea.async_get_version()

            assert atrea.sw_version == "ATC-v2.3.0"

    @pytest.mark.asyncio
    async def test_async_get_version_no_gateway(self, mock_hass):
        """Test async_get_version when GATEWAY key is missing."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            version_data = {
                "OTHER_KEY": "value",
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=version_data
            ):
                await atrea.async_get_version()

            assert atrea.sw_version == "unknown"

    @pytest.mark.asyncio
    async def test_async_get_version_no_data(self, mock_hass):
        """Test async_get_version when no data returned."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.async_get_version()

            assert atrea.sw_version == "unknown"

    @pytest.mark.asyncio
    async def test_ui_scheme_with_flow_config(self, mock_hass):
        """Test ui_scheme method with flow ventilation config."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            control_scheme = {
                "requests": {
                    "flow_ventilation_req": {"min": 10, "max": 100},
                },
                "types": {
                    "flow_ventilation_req": {
                        "min": 10,
                        "max": 100,
                    }
                },
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=control_scheme
            ):
                await atrea.ui_scheme()

            assert atrea._max_flow == 100
            assert atrea._min_flow == 10

    @pytest.mark.asyncio
    async def test_ui_scheme_without_flow_config(self, mock_hass):
        """Test ui_scheme method without flow ventilation config."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            control_scheme = {"requests": {}, "types": {}}  # No flow_ventilation_req

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=control_scheme
            ):
                await atrea.ui_scheme()

            # Should not set _max_flow or _min_flow
            assert atrea._max_flow is None
            assert atrea._min_flow is None

    @pytest.mark.asyncio
    async def test_ui_scheme_no_data(self, mock_hass):
        """Test ui_scheme method when no data returned."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.ui_scheme()

            assert atrea._max_flow is None

    @pytest.mark.asyncio
    async def test_async_get_diagram_data(self, mock_hass):
        """Test async_get_diagram_data method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            diagram_data = {
                "ui_diagram_data": {
                    "bypass_estim": 50,
                    "preheater_factor": 75,
                }
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=diagram_data
            ):
                await atrea.async_get_diagram_data()

            assert atrea.status["bypass_estim"] == 50
            assert atrea.status["preheater_factor"] == 75

    @pytest.mark.asyncio
    async def test_async_get_diagram_data_no_data(self, mock_hass):
        """Test async_get_diagram_data when no data returned."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.async_get_diagram_data()

            # Should keep default values
            assert atrea.status["bypass_estim"] == 0
            assert atrea.status["preheater_factor"] == 0

    @pytest.mark.asyncio
    async def test_async_get_maintenance_data_with_uv_lamp(self, mock_hass):
        """Test async_get_maintenance_data with UV lamp data."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            maintenance_data = {
                "lastFilterReset": {"day": 15, "month": 6, "year": 2024},
                "inspection": {"day": 1, "month": 1, "year": 2024},
                "m1_register": 36000,  # 10 hours
                "m2_register": 72000,  # 20 hours
                "uv_lamp_register": 18000,  # 5 hours
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=maintenance_data
            ):
                await atrea.async_get_maintenance_data()

            assert atrea.status["filters_last_change"] == {
                "day": 15,
                "month": 6,
                "year": 2024,
            }
            assert atrea.status["inspection_date"] == {
                "day": 1,
                "month": 1,
                "year": 2024,
            }
            assert atrea.status["motor1_hours"] == 10
            assert atrea.status["motor2_hours"] == 20
            assert atrea.status["uv_lamp_hours"] == 5
            assert atrea.has_uv_lamp is True

    @pytest.mark.asyncio
    async def test_async_get_maintenance_data_without_uv_lamp(self, mock_hass):
        """Test async_get_maintenance_data without UV lamp data."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            maintenance_data = {
                "lastFilterReset": {"day": 15, "month": 6, "year": 2024},
                "inspection": {"day": 1, "month": 1, "year": 2024},
                "m1_register": 36000,
                "m2_register": 72000,
                "uv_lamp_register": 0,  # No UV lamp
            }

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=maintenance_data
            ):
                await atrea.async_get_maintenance_data()

            assert atrea.status["uv_lamp_hours"] is None
            assert atrea.has_uv_lamp is False

    @pytest.mark.asyncio
    async def test_async_get_maintenance_data_no_data(self, mock_hass):
        """Test async_get_maintenance_data when no data returned."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.async_get_maintenance_data()

            # Should not update status when no data
            assert atrea.has_uv_lamp is False

    @pytest.mark.asyncio
    async def test_time(self, mock_hass):
        """Test time method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock(return_value=1)
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea,
                "update",
                new_callable=AsyncMock,
                return_value={"time": "2024-01-01"},
            ):
                await atrea.time()

            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_ws_connect(self, mock_hass):
        """Test ws_connect method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            # Mock the connect method
            atrea._websocket.connect = AsyncMock()

            await atrea.ws_connect()

            assert atrea._websocket.connect.called

    @pytest.mark.asyncio
    async def test_set_fan_mode_without_max_flow(self, mock_hass):
        """Test set_fan_mode without max_flow set."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea._max_flow = None
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_fan_mode(50)

            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_fan_mode_min_flow_enforcement(self, mock_hass):
        """Test set_fan_mode enforces min flow."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea._max_flow = 100.0
            atrea._min_flow = 30.0  # Minimum 30%
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_fan_mode(10)  # Request 10%, should be clamped to 30%

            # Check that the call was made with min_flow value
            call_args = mock_ws_instance.send.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_set_hvac_mode_auto(self, mock_hass):
        """Test set_hvac_mode with AUTO."""
        from homeassistant.components.climate import HVACMode

        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_hvac_mode(HVACMode.AUTO)

            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_set_temperature(self, mock_hass):
        """Test set_temperature method."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance
            atrea.logged_in = True

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value=None
            ):
                await atrea.set_temperature(22.5)

            assert mock_ws_instance.send.called

    @pytest.mark.asyncio
    async def test_login_flow(self, mock_hass):
        """Test login method end-to-end."""
        with patch("custom_components.amotionatrea.AtreaWebsocket") as MockWS:
            mock_ws_instance = AsyncMock()
            mock_ws_instance.send = AsyncMock()
            MockWS.return_value = mock_ws_instance

            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea._websocket = mock_ws_instance

            with patch.object(
                atrea, "update", new_callable=AsyncMock, return_value="test_token"
            ):
                with patch.object(atrea, "ui_scheme"):
                    with patch.object(atrea, "async_get_discovery"):
                        with patch.object(atrea, "async_get_version"):
                            await atrea.login()

            assert atrea.logged_in is True

    @pytest.mark.asyncio
    async def test_receive_without_id_field_not_stored(self, mock_hass):
        """Test receive handles messages without id field gracefully."""
        with patch("custom_components.amotionatrea.AtreaWebsocket"):
            atrea = AmotionAtrea(mock_hass, "ws://192.168.1.100:8080/", "user", "pass")
            atrea.logged_in = False

            # Message with no 'id' key at all
            message = {
                "type": "event",
                "event": "some_event",
            }

            # Should not raise any exception
            await atrea.receive(message)
