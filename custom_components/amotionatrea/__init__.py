import websocket
import json
import logging

from .const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
    LOGGER,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ Setup connection to atrea """
    ws = websocket.WebSocket()
    try:
        
    except Exception as e:
        raise ConfigEntryNotReady from e
    hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "ws": ws,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True

class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    async def _receive(self):
        message = json.loads(await hass.async_add_executor_job(self._ws.recv))
        # {'args': {'active': False, 'countdown': 0, 'finish': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}, 'sceneId': 0, 'start': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}}, 'event': 'disposable_plan', 'type': 'event'}
        # {'code': 'OK', 'error': None, 'id': None, 'response': {'ui_diagram_data': {'bypass_estim': 100, 'damper_io_state': True, 'fan_eta_operating_time': 24, 'fan_sup_operating_time': 24, 'preheater_active': False, 'preheater_factor': 0, 'preheater_type': 'ELECTRO_PWM'}}, 'type': 'response'}
        if 'id' in message and message['id']:
            self._messages[message['id']] = message['response']

    async def _update(self,message_id=None):
        if message_id:
            # for now loop 10 times(?) before throwing error
            for i in range(10):
                if message_id in self._messages:
                    return self._messages[message_id]
                await self._receive()
            raise Exception("Message with id %d was not received" % message_id)
        await self._receive()

    async def send(self,message):
        msg = json.loads(message)
        msg['id'] = self._msg_id++
        await hass.async_add_executor_job(self._ws.send, msg)
        return msg['id']

    def _login(self)
        msg_id = await self.send('{"endpoint":"login","args":{"username":"%s","password":"%s"}}' % (self._username, self._password))
        token = await self._update(message_id = msg_id)
        await self.send('{"endpoint":"login","args":{"token":"%s"}}' % token)
    

    def __init__(self, host, username, password) -> None:
        """Initialize the Daikin Handle."""
        self._host = host
        self._username = username
        self._password = password
        self._available = True
        self._ws = websocket.WebSocket()
        self._msg_id = 0
        self._messages = {}

        await hass.async_add_executor_job(self._ws.connect, "ws://%s/api/ws" % self._host, origin=self._host, host=self._host)
        await self._login()

