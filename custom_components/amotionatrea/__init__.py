"""Module providing home assistant integration for Amotion Atrea Devices."""

import json
import logging
from datetime import timedelta, datetime
from typing import Any

import asyncio

from homeassistant.const import (
    CONF_URL,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.components.climate import HVACMode

from .const import (
    DOMAIN,
    TIMEOUT,
    BACKGROUND_TASK_LOGIN,
    BACKGROUND_TASK_WS_CONNECT,
)
from .websocket import AtreaWebsocket

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup connection to atrea."""
    try:
        atrea = AmotionAtrea(
            hass,
            entry.data[CONF_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD]
        )
    except Exception as e:
        raise ConfigEntryNotReady(f"Failed to initialize Atrea: {e}") from e

    coordinator = AmotionAtreaCoordinator(hass, atrea)
    await coordinator.async_config_entry_first_refresh()
    LOGGER.debug("Setup completed successfully")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class AmotionAtreaCoordinator(DataUpdateCoordinator):
    """AmotionAtrea custom coordinator."""

    def __init__(self, hass: HomeAssistant, aatrea: "AmotionAtrea") -> None:
        super().__init__(
            hass,
            LOGGER,
            name="AmotionAtrea",
            update_interval=timedelta(seconds=30),
            always_update=True
        )
        self.aatrea: AmotionAtrea = aatrea

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(TIMEOUT):
                return await self.aatrea.fetch()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    async def on_close(self) -> None:
        """Reset message counter."""
        LOGGER.debug("Reset counter")
        self._msg_id = 0

    async def on_connect(self) -> None:
        """Handle WebSocket connection."""
        LOGGER.debug("Connected")
        self._hass.async_create_background_task(
            self.login(), BACKGROUND_TASK_LOGIN
        )

    async def receive(self, message: dict[str, Any]) -> None:
        """Process incoming WebSocket messages.

        Args:
            message: The parsed JSON message from the WebSocket.

        Raises:
            ConfigEntryNotReady: If authentication fails.
        """
        LOGGER.debug("receive message: %s", message)

        # Validate message structure
        if not isinstance(message, dict):
            LOGGER.warning("Received non-dict message: %s", message)
            return

        # Handle response messages with ID
        if 'id' in message and message['id'] is not None:
            # Check for required fields before storing
            if 'response' not in message:
                return

            if message.get('code') == 'UNAUTHORIZED':
                LOGGER.warning("Device returned UNAUTHORIZED response")
                raise ConfigEntryNotReady("Authentication failed with device")

            self._messages[message['id']] = message.get('response')
            self._messages[message['id']] = message.get('response')

        # Handle event messages
        elif (
            message.get('type') == 'event'
            and message.get('event') == 'ui_info'
            and self.logged_in
        ):
            await self._update_status(message)

    async def _update_status(self, message: dict[str, Any]) -> None:
        """Update device status from WebSocket event message.

        Args:
            message: The ui_info event message from the device.
        """
        args = message.get('args', {})
        unit = args.get('unit', {})
        requests = args.get('requests', {})

        self.status['current_temperature'] = unit.get('temp_sup')
        self.status['setpoint'] = requests.get('temp_request')
        self.status['temp_oda'] = unit.get('temp_oda')
        self.status['temp_ida'] = unit.get('temp_ida')
        self.status['temp_eha'] = unit.get('temp_eha')
        self.status['temp_eta'] = unit.get('temp_eta')
        self.status['temp_sup'] = unit.get('temp_sup')
        self.status['season_current'] = unit.get('season_current')
        self.status['last_update'] = datetime.now()

        if self._max_flow:
            max_flow_normalized = float(self._max_flow) / 100
            self.status['fan_mode'] = round(
                float(requests.get('flow_ventilation_req', 0)) / max_flow_normalized, -1
            )
            self.status['fan_eta_factor'] = round(
                float(unit.get('flow_eta', 0)) / max_flow_normalized, -1
            )
            self.status['fan_sup_factor'] = round(
                float(unit.get('flow_sup', 0)) / max_flow_normalized, -1
            )
        else:
            self.status['fan_eta_factor'] = unit.get('fan_eta_factor')
            self.status['fan_sup_factor'] = unit.get('fan_sup_factor')
            self.status['fan_mode'] = requests.get('fan_power_req')

    async def update(self, message_id: int | None = None) -> dict[str, Any] | None:
        """Wait for a specific message ID response.

        Args:
            message_id: The ID of the message to wait for.

        Returns:
            The response message or None if timeout.
        """
        LOGGER.debug("update %s", message_id)
        if message_id is not None:
            try:
                async with asyncio.timeout(30):
                    for _ in range(30):
                        if message_id in self._messages:
                            msg = self._messages[message_id]
                            del self._messages[message_id]
                            LOGGER.debug("Found message %s", msg)
                            return msg
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                LOGGER.debug("Timeout while waiting for message_id: %s", message_id)
        return None

    async def fetch(self) -> dict[str, Any]:
        """Fetch current device status."""
        if self._max_flow:
            await self.time()

        LOGGER.debug("Last update: %s", self.status['last_update'])

        # Refresh status if unavailable or older than 2 minutes
        if (
            self.status['current_temperature'] is None
            or datetime.now() - self.status['last_update'] >= timedelta(minutes=2)
        ):
            try:
                async with asyncio.timeout(60):
                    while not self.logged_in:
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                LOGGER.debug("Timeout while waiting for login")

            response_id = await self.send('{"endpoint": "ui_info", "args": null}')
            message = await self.update(response_id)
            if message:
                # Merge message structure for unified status update
                message["args"] = message
                await self._update_status(message)

        # Get maintenance data and diagram data every 5 minutes
        if (
            datetime.now() - self.status['last_maintenance_update'] >= timedelta(minutes=5)
        ):
            await self.async_get_maintenance_data()
            await self.async_get_diagram_data()

        return self.status

    async def send(self, message: str) -> int:
        """Send a JSON message via WebSocket.

        Args:
            message: The JSON string to send.

        Returns:
            The message ID for tracking responses.

        Raises:
            ConfigEntryNotReady: If connection times out.
        """
        msg = json.loads(message)
        msg['id'] = self._msg_id = self._msg_id + 1
        LOGGER.debug("MSG: %s", msg)

        try:
            async with asyncio.timeout(TIMEOUT):
                await self._websocket.send(json.dumps(msg))
        except TimeoutError as err:
            LOGGER.debug("Connection to %s timed out", self._url)
            raise ConfigEntryNotReady from err

        return msg['id']

    async def async_get_discovery(self) -> None:
        """Fetch device discovery information."""
        response_id = await self.send('{"endpoint": "discovery", "args": null}')
        discovery_data = await self.update(response_id)
        if discovery_data:
            self.model = discovery_data.get('type', 'Unknown')
            self.serial = discovery_data.get('production_number', 'Unknown')
            self.brand = discovery_data.get('brand', 'Atrea')
            self.name = discovery_data.get('name', 'Atrea')

    async def async_get_version(self) -> None:
        """Fetch device firmware version."""
        response_id = await self.send('{"endpoint": "version", "args": null}')
        version_data = await self.update(response_id)
        if version_data:
            gateway_info = version_data.get('GATEWAY', {})
            self.sw_version = gateway_info.get('version', 'unknown')
        else:
            self.sw_version = 'unknown'

    async def login(self) -> None:
        """Authenticate with the device and initialize connection."""
        LOGGER.info("Starting login process")
        try:
            msg_id = await self.send(
                f'{{"endpoint":"login","args":{{"username":"{self._username}","password":"{self._password}"}}}}'
            )
            token = await self.update(message_id=msg_id)
            LOGGER.debug("Token received: %s", token)

            if token is None:
                raise ConfigEntryNotReady("Login timeout - no token received")

            # Second login with token
            await self.send(f'{{"endpoint":"login","args":{{"token":"{token}"}}}}')

            await self.ui_scheme()
            self.logged_in = True

            await self.async_get_discovery()
            await self.async_get_version()

            LOGGER.info("Login successful")
        except ConfigEntryNotReady:
            LOGGER.error("Login failed: %s")
            raise
        except Exception as e:
            LOGGER.exception("Unexpected error during login")
            raise ConfigEntryNotReady(f"Login error: {e}") from e

    async def ui_scheme(self) -> None:
        """Fetch UI control scheme to determine fan mode capabilities."""
        response_id = await self.send('{"endpoint": "ui_control_scheme", "args": null}')
        control_scheme = await self.update(response_id)
        if control_scheme and 'flow_ventilation_req' in control_scheme.get('requests', {}):
            flow_config = control_scheme['types']['flow_ventilation_req']
            self._max_flow = flow_config.get('max')
            self._min_flow = flow_config.get('min')

    async def async_get_diagram_data(self) -> None:
        """Fetch diagram data including bypass_estim from the server."""
        response_id = await self.send('{"endpoint": "ui_diagram_data", "args": null}')
        diagram_response = await self.update(response_id)
        if diagram_response:
            ui_diagram = diagram_response.get('ui_diagram_data', {})
            self.status['bypass_estim'] = ui_diagram.get('bypass_estim', 0)
            self.status['preheater_factor'] = ui_diagram.get('preheater_factor', 0)

    async def async_get_maintenance_data(self) -> None:
        """Get maintenance information like filter change dates and motor hours."""
        response_id = await self.send('{"endpoint": "moments/get", "args": null}')
        moment_data = await self.update(response_id)

        if moment_data:
            self.status['last_maintenance_update'] = datetime.now()
            self.status['filters_last_change'] = moment_data.get('lastFilterReset', {})
            self.status['inspection_date'] = moment_data.get('inspection', {})

            # Motor operating hours (convert from seconds to hours)
            self.status['motor1_hours'] = round(moment_data.get('m1_register', 0) / 3600)
            self.status['motor2_hours'] = round(moment_data.get('m2_register', 0) / 3600)

            # UV lamp operating hours (optional feature)
            uv_lamp_register = moment_data.get('uv_lamp_register', 0)
            if uv_lamp_register and uv_lamp_register > 0:
                self.status['uv_lamp_hours'] = round(uv_lamp_register / 3600)
                self.has_uv_lamp = True
            else:
                self.status['uv_lamp_hours'] = None
                self.has_uv_lamp = False

    async def time(self) -> None:
        """Fetch device time."""
        response_id = await self.send('{"endpoint":"time", "args": null}')
        message = await self.update(response_id)
        LOGGER.debug("TIME %s", message)

    async def ws_connect(self) -> None:
        """Connect the websocket and initialize session."""
        await self._websocket.connect(self.on_connect, self.receive, self.on_close)

    async def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode percentage.

        Args:
            fan_mode: Fan mode as string (e.g., "50" for 50%).
        """
        if self._max_flow:
            flow_request = (float(self._max_flow) / 100) * int(fan_mode)
            flow_request = max(flow_request, self._min_flow)
            control = json.dumps({'variables': {"flow_ventilation_req": int(flow_request)}})
        else:
            control = json.dumps({'variables': {"fan_power_req": int(fan_mode)}})
        response_id = await self.send(f'{{ "endpoint": "control", "args": {control} }}')
        await self.update(response_id)

    async def set_temperature(self, temperature: float) -> None:
        """Set target temperature.

        Args:
            temperature: Target temperature in Celsius.
        """
        control = json.dumps({'variables': {'temp_request': int(temperature)}})
        response_id = await self.send(f'{{ "endpoint": "control", "args": {control} }}')
        await self.update(response_id)

    async def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode.

        Args:
            hvac_mode: The desired HVAC mode.

        Note:
            FIXME: This should be setting based on UI control scheme.
        """
        mode = 'OFF'
        match hvac_mode:
            case HVACMode.HEAT_COOL:
                mode = 'VENTILATION'
            case HVACMode.AUTO:
                mode = 'AUTO'

        control = json.dumps({'variables': {"work_regime": mode}})
        response_id = await self.send(f'{{ "endpoint": "control", "args": {control} }}')
        await self.update(response_id)

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        username: str,
        password: str
    ) -> None:
        """Initialize the AmotionAtrea device.

        Args:
            hass: Home Assistant instance.
            url: Base URL of the Atrea device.
            username: Username for authentication.
            password: Password for authentication.
        """
        self._hass: HomeAssistant = hass
        self._url: str = url
        self._username: str = username
        self._password: str = password
        self._available: bool = True
        self.logged_in: bool = False
        self._msg_id: int = 0
        self._messages: dict[int, dict[str, Any]] = {}
        self._websocket: AtreaWebsocket = AtreaWebsocket(url)
        self._max_flow: float | None = None
        self._min_flow: float | None = None
        self.has_uv_lamp: bool = False

        self.status: dict[str, Any] = {
            'state': None,
            'current_temperature': None,
            'setpoint': None,
            'mode': None,
            'current_hvac_mode': HVACMode.AUTO,
            'fan_mode': None,
            'temp_oda': None,
            'temp_ida': None,
            'temp_eha': None,
            'fan_eta_factor': None,
            'fan_sup_factor': None,
            'temp_sup': None,
            'temp_eta': None,
            'season_current': None,
            'last_update': None,
            'has_heater': False,
            'has_cooler': False,
            'filters_last_change': {},
            'inspection_date': {},
            'motor1_hours': 0,
            'motor2_hours': 0,
            'uv_lamp_hours': None,
            'last_maintenance_update': datetime.min,
            'bypass_estim': 0,
            'preheater_factor': 0,
        }

        self.model: str | None = None
        self.sw_version: str | None = None
        self.serial: str | None = None
        self.brand: str = "Atrea"
        self.name: str = "Atrea"

        # Start WebSocket connection in background
        self._hass.async_create_background_task(
            self.ws_connect(), BACKGROUND_TASK_WS_CONNECT
        )
