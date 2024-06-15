import websocket
import json
import logging
import asyncio


from .const import (
     DOMAIN,
     TIMEOUT,
     LOGGER,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ Setup connection to atrea """
    try:
        atrea = AmotionAtrea(hass, entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        await atrea.login()
    except Exception as e:
        raise ConfigEntryNotReady from e
    hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "atrea": atrea,
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
        try:
            async with asyncio.timeout(TIMEOUT):
                message = json.loads(await self._hass.async_add_executor_job(self._ws.recv))
        except TimeoutError as err:
            LOGGER.debug("Connection to %s timed out", self._host)
            raise ConfigEntryNotReady from err

        # {'args': {'active': False, 'countdown': 0, 'finish': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}, 'sceneId': 0, 'start': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}}, 'event': 'disposable_plan', 'type': 'event'}
        # {'code': 'OK', 'error': None, 'id': None, 'response': {'ui_diagram_data': {'bypass_estim': 100, 'damper_io_state': True, 'fan_eta_operating_time': 24, 'fan_sup_operating_time': 24, 'preheater_active': False, 'preheater_factor': 0, 'preheater_type': 'ELECTRO_PWM'}}, 'type': 'response'}
        if 'id' in message and message['id']:
            self._messages[message['id']] = message['response']
            LOGGER.debug(message)

    async def update(self,message_id=None):
        if message_id:
            # for now loop 10 times(?) before throwing error
            for i in range(10):
                if message_id in self._messages:
                    msg = self._messages[message_id]
                    del self._messages[message_id]
                    return msg
                await self._receive()
            raise Exception("Message with id %s was not received" % message_id)
        await self._receive()

    async def send(self,message):
        # sends message and returns id you can look for in update
        LOGGER.debug(message)
        msg = json.loads(message)
        msg['id'] = self._msg_id = self._msg_id + 1
        LOGGER.debug("MSG: %s" % msg)

        try:
            async with asyncio.timeout(TIMEOUT):
                await self._hass.async_add_executor_job(self._ws.send, json.dumps(msg))
        except TimeoutError as err:
            LOGGER.debug("Connection to %s timed out", self._host)
            raise ConfigEntryNotReady from err

        return msg['id']

    async def login(self):
        LOGGER.debug("sending login to get token")
        msg_id = await self.send('{"endpoint":"login","args":{"username":"%s","password":"%s"}}' % (self._username, self._password))
        token = await self.update(message_id = msg_id)
        LOGGER.debug("token is")
        await self.send('{"endpoint":"login","args":{"token":"%s"}}' % token)
    
    def __init__(self, hass, host, username, password) -> None:
        """Initialize the Daikin Handle."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._available = True
        # Last resort debug uncomment below:
        # websocket.enableTrace(True)
        self._ws = websocket.WebSocket()
        self._msg_id = 0
        self._messages = {}
        self._ws.connect("ws://%s/api/ws" % self._host, origin=self._host, host=self._host)
