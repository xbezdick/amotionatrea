import json
import logging
import asyncio
from datetime import timedelta

import websockets

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.components.climate.const import ( HVACMode,
)


from .const import (
     DOMAIN,
     TIMEOUT,
     LOGGER,
)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup connection to atrea."""
    try:
        atrea = AmotionAtrea(
            hass,
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD]
        )
        entry.async_create_background_task(
            hass, atrea.ws_connect(), "amotionatrea-ws_connect"
        )
        entry.async_create_background_task(
            hass, atrea.login(), "amotionatrea-login"
        )
        
        
    except Exception as e:
        raise ConfigEntryNotReady from e

    coordinator = AmotionAtreaCoordinator(hass, atrea)
    await coordinator.async_config_entry_first_refresh()
    LOGGER.debug("thread is on")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)



class AtreaWebsocket:
    def __init__(self, host, username, password):
        self._host = self._validate_and_format_uri(host)
        self._username = username
        self._password = password
        self._websocket = None
        self.reconnect_delay = 2
        self._connected = False
        self._msg_id = 0  
        self._messages = {}  #

    def _validate_and_format_uri(self, host):
        """Validate and format the URI to ensure it has the correct scheme."""
        if not host.startswith("ws://") and not host.startswith("wss://"):
            host = "ws://" + host +"/api/ws"
        return host

    async def connect(self, on_data, on_close):
        """Establish a websocket connection."""
        while True:
            try:
                async with websockets.connect(
                    self._host, ping_interval=None, ping_timeout=None
                ) as websocket:
                    self._websocket = websocket
                    self._connected = True
                    LOGGER.info("WebSocket connection established")
                    self._msg_id = 0  # Reset message ID after connection
                    await self.handle_messages(websocket, on_data)
            except (websockets.exceptions.ConnectionClosedError, 
                    websockets.exceptions.ConnectionClosedOK) as e:
                LOGGER.debug("Connection closed, retrying...")
                self._connected = False
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)
            except Exception as err:
                LOGGER.debug(f"Unexpected error: {err}")
                self._connected = False
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    async def handle_messages(self, websocket, on_data):
        """Handle incoming WebSocket messages."""
        try:
            async for message in websocket:
                try:
                    decoded_message = json.loads(message)
                    LOGGER.debug(f"Received message: {decoded_message}")
                    if 'id' in decoded_message:
                        # Check if the message ID is expected
                        # LOGGER.debug(f"All Messages : {self._messages}")
                        # if decoded_message['id'] in self._messages:
                        self._messages[decoded_message['id']] = decoded_message
                        await on_data(decoded_message)
                        # else:
                        #     LOGGER.debug(f"Unexpected message ID: {decoded_message['id']}")
                    else:
                        LOGGER.debug(f"Message without ID: {decoded_message}")
                except json.JSONDecodeError as e:
                    LOGGER.error(f"Error decoding message: {e}")
                except Exception as e:
                    LOGGER.error(f"Error handling message: {e}")
        except websockets.exceptions.ConnectionClosedError as e:
            LOGGER.error(f"Connection closed: {e}")
            self._connected = False
            raise e
        except Exception as e:
            LOGGER.error(f"Error handling messages: {e}")
            self._connected = False

    async def send(self, message):
        """Send a message through the websocket."""
        if not self._connected:
            raise Exception("WebSocket is not connected")
        self._msg_id += 1  # Increment message ID
        msg = json.loads(message)
        msg['id'] = self._msg_id  # Add message ID to the message
        LOGGER.debug(f"Sending to ws {json.dumps(msg)}")
        await self._websocket.send(json.dumps(msg))
        self._messages[self._msg_id] = None  # Initialize the message ID in the _messages dictionary
        LOGGER.debug(f"Initialized message ID {self._msg_id} in _messages: {self._messages}")
        return self._msg_id  # Return the message ID

    async def close(self):
        """Close the websocket connection."""
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None
            self._connected = False
            LOGGER.info("WebSocket connection closed")

class AmotionAtreaCoordinator(DataUpdateCoordinator):
    """AmotionAtrea custom coordinator."""

    def __init__(self, hass, aatrea):
        super().__init__(
            hass,
            LOGGER,
            name="AmotionAtrea",
            update_interval=timedelta(seconds=30),
            always_update=True
        )
        self.aatrea = aatrea

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        LOGGER.debug("UPDATE CALLED")
        try:
            async with asyncio.timeout(TIMEOUT):
                ui_info_data = await self.aatrea.fetch("ui_info")
                version_data = await self.aatrea.fetch("version")
                discovery_data = await self.aatrea.fetch("discovery")
                LOGGER.debug(f"Fetched ui_info data: {ui_info_data}")
                LOGGER.debug(f"Fetched version data: {version_data}")
                LOGGER.debug(f"Fetched discovery data: {discovery_data}")
                return self.process_data(ui_info_data, version_data, discovery_data)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
    
    def process_data(self, ui_info_data, version_data, discovery_data):
        """Process the fetched data and update sensor values."""
        data = {}
        if ui_info_data and 'response' in ui_info_data:
            response = ui_info_data['response']
            LOGGER.debug(f"ui_info response: {response}")
            current_temperature = response.get('unit', {}).get('temp_ida')
            setpoint = response.get('requests', {}).get('temp_request')
            LOGGER.debug(f"Extracted current_temperature: {current_temperature}, setpoint: {setpoint}")
            if current_temperature is None:
                LOGGER.warning("current_temperature is None")
            if setpoint is None:
                LOGGER.warning("setpoint is None")
            data.update({
                'current_temperature': current_temperature,
                'setpoint': setpoint,
                'ui_info_data': response
            })
        if version_data and 'response' in version_data:
            response = version_data['response']
            LOGGER.debug(f"version response: {response}")
            device_type = response.get('COMPACT')
            software_version = response.get('GATEWAY', {}).get('version')
            LOGGER.debug(f"Extracted device_type: {device_type}, software_version: {software_version}")
            data.update({
                'device_type': device_type,
                'software_version': software_version,
                'version_data': response
            })
        if discovery_data and 'response' in discovery_data:
            response = discovery_data['response']
            LOGGER.debug(f"discovery response: {response}")
            name = response.get('name')
            type = response.get('type')
            LOGGER.debug(f"Extracted name: {name}")
            data.update({
                'name': name,
                'type': type,
                'discovery_data': response
            })
        return data



class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    def __init__(self, hass, host, username, password):
        self.hass = hass
        self.status = {
            'state': None,
            'current_temperature': None,
            'setpoint': None,
            'mode': None,
            'current_hvac_mode': HVACMode.AUTO,
            'fan_mode': None,
            'temp_oda': None,
            'temp_ida': None,
            'temp_eha': None,
            'temp_sup': None,
            'temp_eta': None,
            'fan_eta_factor': None,
            'fan_sup_factor': None
        }
        self._host = host
        self._username = username
        self._password = password
        self._websocket = AtreaWebsocket(host, username, password)
        self._messages = {}
        self.logged_in = False
        self._max_flow = None
        self._min_flow = None

    async def fetch(self, endpoint, args=None):
        for i in range(10):
            if self.logged_in:
                break
            await asyncio.sleep(1)
        else:
            raise Exception("Not logged in")
        msg_id = await self._websocket.send(json.dumps({"endpoint": endpoint, "args": args}))
        response = await self.update(message_id=msg_id)
        return response

    async def ws_connect(self):
        """Connect to the websocket."""
        await self._websocket.connect(self.receive, self.on_close)

    async def login(self):
        """Login to the websocket."""
        LOGGER.debug("sending login to get token")
        for i in range(10):
            if self._websocket._connected:
                break
            await asyncio.sleep(1)
        else:
            raise Exception("WebSocket is not connected")
        try:
            msg_id = await self._websocket.send(
                '{"endpoint":"login","args":{"username":"%s","password":"%s"}}' % (self._username, self._password))
            token_response = await self.update(message_id=msg_id)
            token = token_response if token_response else None
            LOGGER.debug("token is %s", token)
            if not token:
                raise Exception("Failed to retrieve token")
            msg_id = await self._websocket.send('{"endpoint":"login","args":{"token":"%s"}}' % token)
            # await self.ui_scheme()
            self.logged_in = True
            self._websocket._msg_id = 1  # Reset message ID after successful login

        except Exception as e:
            LOGGER.error(f"Login failed: {e}")
            self.logged_in = False

    async def ui_scheme(self):
        response_id = await self._websocket.send('{ "endpoint": "ui_info_scheme", "args": null }')
        message = await self.update(message_id=response_id)
        if "flow_ventilation_req" in message["requests"]:
            response_id = await self._websocket.send('{ "endpoint": "ui_control_scheme", "args": null }')
            message = await self.update(message_id=response_id)
            self._max_flow = message["types"]["flow_ventilation_req"]["max"]
            self._min_flow = message["types"]["flow_ventilation_req"]["min"]

    async def receive(self, message):
        LOGGER.debug("receive message: %s" % message)
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except json.JSONDecodeError as e:
                LOGGER.error(f"Error decoding message: {e}")
                return
        if message.get("code") == "UNAUTHORIZED":
            # The token may have expired
            raise ConfigEntryNotReady
        if 'id' in message and message['id']:
            LOGGER.debug("ID IS: %s" % message['id'])
            self._messages[message['id']] = message['response']
            LOGGER.debug(message['response'])
            LOGGER.debug(self._messages)
        elif message['type'] == 'event' and message['event'] == 'ui_info' and self.logged_in:
            args = message.get('args', {})
            unit = args.get('unit', {})
            requests = args.get('requests', {})
            if unit and requests:
                logging.info(f"current_temperature: {unit.get('temp_sup')}")
                self.status['current_temperature'] = unit.get("temp_sup")
                self.status['setpoint'] = requests.get("temp_request")
                self.status['temp_oda'] = unit.get('temp_oda')
                self.status['temp_ida'] = unit.get('temp_ida')
                self.status['temp_eha'] = unit.get('temp_eha')
                self.status['temp_eta'] = unit.get('temp_eta')
                self.status['temp_sup'] = unit.get('temp_sup')
                self.status["current_hvac_mode"] = unit.get('season_current')
                if self._max_flow:
                    self.status['fan_mode'] = round(float(requests.get("fan_power_req", 0)) /
                                                    (float(self._max_flow) / 100), -1)
                    self.status['fan_eta_factor'] = round(float(unit.get("flow_eta", 0)) /
                                                          (float(self._max_flow) / 100), -1)
                    self.status['fan_sup_factor'] = round(float(unit.get("flow_sup", 0)) /
                                                          (float(self._max_flow) / 100), -1)
                else:
                    self.status['fan_eta_factor'] = unit.get('fan_eta_factor')
                    self.status['fan_sup_factor'] = unit.get('fan_sup_factor')
                    self.status['fan_mode'] = requests.get("fan_power_req")
            else:
                LOGGER.error("Missing 'unit' or 'requests' in message")

    async def set_fan_mode(self, fan_mode):
        if self._max_flow:
            flow_request = (float(self._max_flow)/100)*int(fan_mode)
            if flow_request < self._min_flow:
                flow_request = self._min_flow
            control = {'variables': {"flow_ventilation_req": int(flow_request)}}
        else:
            control = {'variables': {"fan_power_req": int(fan_mode)}}
        response_id = await self._websocket.send('{ "endpoint": "control", "args": %s }' % json.dumps(control))
        await self.update(response_id)

    async def set_temperature(self, temperature):
        """Set the target temperature."""
        LOGGER.debug(f"Setting temperature to {temperature}")
        control = {'variables': {"temp_request": float(temperature)}}
        response_id = await self._websocket.send('{ "endpoint": "control", "args": %s }' % json.dumps(control))
        await self.update(response_id)

    async def set_mode(self, mode):
        """Set the HVAC mode."""
        LOGGER.debug(f"Setting mode to {mode}")
        control = {'variables': {"season_current": mode}}
        response_id = await self._websocket.send('{ "endpoint": "control", "args": %s }' % json.dumps(control))
        await self.update(response_id)

    async def on_close(self):
        """Handle websocket close."""
        self.logged_in = False
        LOGGER.info("WebSocket connection closed")

    async def update(self, message_id=None):
        """Update the data."""
        LOGGER.debug("update %s" % message_id)
        if message_id:
            for i in range(10):
                if message_id in self._websocket._messages:
                    msg = self._websocket._messages[message_id]
                    if msg is not None:
                        del self._websocket._messages[message_id]
                        LOGGER.debug("Found message %s" % msg)
                        return msg
                LOGGER.debug("Not found message_id: %s in %s attempt %s" % (message_id, self._websocket._messages, i))
                await asyncio.sleep(1)
            LOGGER.debug(f"Update message: {self.receive}, {self.on_close}")
        return None
