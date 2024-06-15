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

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
)


PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ Setup connection to atrea """
    try:
        atrea = AmotionAtrea(hass, entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        await atrea.login()
    except Exception as e:
        raise ConfigEntryNotReady from e


    coordinator = AmotionAtreaCoordinator(hass, atrea)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


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
        try:
            async with asyncio.timeout(TIMEOUT):
                return await self.aatrea.update()
        # TODO: FIXME: rework config_flow
        #except ApiAuthError as err:
        #    # Raising ConfigEntryAuthFailed will cancel future updates
        #    # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #    raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    async def _receive(self):
        try:
            async with asyncio.timeout(TIMEOUT):
                message = json.loads(await self._hass.async_add_executor_job(self._ws.recv))
                LOGGER.debug(message)
        except TimeoutError as err:
            LOGGER.debug("Connection to %s timed out", self._host)
            raise ConfigEntryNotReady from err

        # {'args': {'active': False, 'countdown': 0, 'finish': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}, 'sceneId': 0, 'start': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}}, 'event': 'disposable_plan', 'type': 'event'}
        # {'code': 'OK', 'error': None, 'id': None, 'response': {'ui_diagram_data': {'bypass_estim': 100, 'damper_io_state': True, 'fan_eta_operating_time': 24, 'fan_sup_operating_time': 24, 'preheater_active': False, 'preheater_factor': 0, 'preheater_type': 'ELECTRO_PWM'}}, 'type': 'response'}
        # {'args': {'requests': {'fan_power_req': 30, 'temp_request': 18.5, 'work_regime': 'VENTILATION'}, 'states': {'active': {}}, 'unit': {'fan_eta_factor': 30, 'fan_sup_factor': 30, 'mode_current': 'NORMAL', 'season_current': 'NON_HEATING', 'temp_eha': 23.9, 'temp_eta': 23.9, 'temp_ida': 23.9, 'temp_oda': 22.9, 'temp_oda_mean': 22.25, 'temp_sup': 23.3}}, 'event': 'ui_info', 'type': 'event'}

        if 'id' in message and message['id']:
            self._messages[message['id']] = message['response']
        elif message['type'] == 'event' and message['event'] == 'ui_info':
            self.status['current_temperature'] = message["args"]["unit"]["temp_sup"]
            self.status['fan_mode'] = message["args"]["requests"]["fan_power_req"]
            self.status['setpoint'] = message["args"]["requests"]["temp_request"]
            self.status['temp_oda'] = message["args"]["unit"]['temp_oda']
            self.status['temp_ida'] = message["args"]["unit"]['temp_ida']
            self.status['temp_eha'] = message["args"]["unit"]['temp_eha']
            self.status['fan_eta_factor'] = message["args"]["unit"]['fan_eta_factor']
            self.status['fan_sup_factor'] = message["args"]["unit"]['fan_sup_factor']


    async def update(self,message_id=None):
        if message_id:
            # for now loop 10 times(?) before throwing error
            for i in range(10):
                if message_id in self._messages:
                    msg = self._messages[message_id]
                    del self._messages[message_id]
                    return msg
                await self._receive()
                await asyncio.sleep(1)
            raise Exception("Message with id %s was not received" % message_id)
        await self._receive()

    async def fetch(self):
        if self.status['current_temperature'] is None:
            response_id = await self.send('{ "endpoint": "ui_info", "args": null }')
            message = await self._atrea.update(response_id)
            self.status['current_temperature'] = message["unit"]["temp_sup"]
            self.status['fan_mode'] = message["requests"]["fan_power_req"]
            self.status['setpoint'] = message["requests"]["temp_request"]
            self.status['temp_oda'] = message["unit"]['temp_oda']
            self.status['temp_ida'] = message["unit"]['temp_ida']
            self.status['temp_eha'] = message["unit"]['temp_eha']
            self.status['fan_eta_factor'] = message["unit"]['fan_eta_factor']
            self.status['fan_sup_factor'] = message["unit"]['fan_sup_factor']
        else:
            self.update()

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


        self.status = {
          'state': None,
          'current_temperature': None,
          'setpoint': None,
          'mode': None,
          'current_hvac_mode': HVAC_MODE_AUTO,
          'fan_mode': None,
          'temp_oda': None,
          'temp_ida': None,
          'temp_eha': None,
          'fan_eta_factor': None,
          'fan_sup_factor': None
        }
