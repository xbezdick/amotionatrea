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

from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
)


from .const import (
     DOMAIN,
     TIMEOUT,
     LOGGER,
)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ Setup connection to atrea """
    try:
        atrea = AmotionAtrea(hass,
                             entry.data[CONF_HOST],
                             entry.data[CONF_USERNAME],
                             entry.data[CONF_PASSWORD])
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
    def __init__(self, host):
        self._host = host
        self._websocket = None

    async def send(self, message):
        LOGGER.debug("Sending to ws %s" % message)
        for i in range(120):
            if self._websocket:
                await self._websocket.send(message)
                break
            await asyncio.sleep(1)

    async def connect(self, on_data, on_close):
        for i in range(10):
            try:
                async with websockets.connect(
                    "ws://%s/api/ws" % self._host, ping_interval=None, ping_timeout=None, logger=LOGGER
                ) as websocket:
                    self._websocket = websocket
                    async for message in websocket:
                        LOGGER.debug("Received %s" % message)
                        if "UNAUTHORIZED" in message.get("code"):
                            raise websockets.ConnectionClosed
                        await on_data(json.loads(message))
            except websockets.ConnectionClosed:
                LOGGER.debug("Connection closed, retrying...")
                await asyncio.sleep(1)  # 
            except Exception as err:
                LOGGER.debug(err)
                await on_close()
                return
            asyncio.sleep(1)

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
                return await self.aatrea.fetch()
        # TODO: FIXME: rework config_flow
        #except ApiAuthError as err:
        #    # Raising ConfigEntryAuthFailed will cancel future updates
        #    # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #    raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")



class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    async def receive(self, message):
        LOGGER.debug("receive message: %s" % message)
        # {'args': {'active': False, 'countdown': 0, 'finish': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}, 'sceneId': 0, 'start': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}}, 'event': 'disposable_plan', 'type': 'event'}
        # {'code': 'OK', 'error': None, 'id': None, 'response': {'ui_diagram_data': {'bypass_estim': 100, 'damper_io_state': True, 'fan_eta_operating_time': 24, 'fan_sup_operating_time': 24, 'preheater_active': False, 'preheater_factor': 0, 'preheater_type': 'ELECTRO_PWM'}}, 'type': 'response'}
        # {'args': {'requests': {'fan_power_req': 30, 'temp_request': 18.5, 'work_regime': 'VENTILATION'}, 'states': {'active': {}}, 'unit': {'fan_eta_factor': 30, 'fan_sup_factor': 30, 'mode_current': 'NORMAL', 'season_current': 'NON_HEATING', 'temp_eha': 23.9, 'temp_eta': 23.9, 'temp_ida': 23.9, 'temp_oda': 22.9, 'temp_oda_mean': 22.25, 'temp_sup': 23.3}}, 'event': 'ui_info', 'type': 'event'}
        if 'id' in message and message['id']:
            LOGGER.debug("ID IS: %s" % message['id'])
            self._messages[message['id']] = message['response']
            LOGGER.debug(message['response'])
            LOGGER.debug(self._messages)
        elif message['type'] == 'event' and message['event'] == 'ui_info' and self.logged_in:
            self.status['current_temperature'] = message["args"]["unit"]["temp_sup"]
            self.status['setpoint'] = message["args"]["requests"]["temp_request"]
            self.status['temp_oda'] = message["args"]["unit"]['temp_oda']
            self.status['temp_ida'] = message["args"]["unit"]['temp_ida']
            self.status['temp_eha'] = message["args"]["unit"]['temp_eha']
            self.status['temp_eta'] = message["args"]["unit"]['temp_eta']
            self.status['temp_sup'] = message["args"]["unit"]['temp_sup']
            self.status['season_current'] = message["args"]["unit"]['season_current']
            if self._max_flow:
                self.status['fan_mode'] = round( float(message["args"]
                                                              ["requests"]
                                                              ["flow_ventilation_req"])/
                                                (float(self._max_flow)/100), -1
                                               )
                self.status['fan_eta_factor'] = round( float(message["args"]["unit"]["flow_eta"])/
                                                (float(self._max_flow)/100), -1
                                               )
                self.status['fan_sup_factor'] = round( float(message["args"]["unit"]["flow_sup"])/
                                                (float(self._max_flow)/100), -1
                                               )
            else:
                self.status['fan_eta_factor'] = message["args"]["unit"]['fan_eta_factor']
                self.status['fan_sup_factor'] = message["args"]["unit"]['fan_sup_factor']
                self.status['fan_mode'] = message["args"]["requests"]["fan_power_req"]



    async def update(self,message_id=None):
        LOGGER.debug("update %s" % message_id)
        if message_id:
            # for now loop 10 times(?) before throwing error
            for i in range(10):
                if message_id in self._messages:
                    msg = self._messages[message_id]
                    del self._messages[message_id]
                    LOGGER.debug("Found message %s" % msg)
                    return msg
                LOGGER.debug("Not found message_id: %s in %s attempt %s" %(message_id,
                                                                           self._messages,
                                                                           i))
                await asyncio.sleep(1)
            LOGGER.debug(f"RECONNECTING, {self.receive}, {self.on_close}")
            await self.ws_connect()
            #raise ConfigEntryNotReady

    async def fetch(self):
        for i in range(10):
            if self.logged_in:
                break
            await asyncio.sleep(1)
        else:
            raise ConfigEntryNotReady
        response_id = await self.send('{ "endpoint": "ui_info", "args": null }')
        LOGGER.info(f"Got None in response, RECONNECTING, response_id {response_id}.")
        message = await self.update(response_id)
        self.status['current_temperature'] = message["unit"]["temp_sup"]
        self.status['setpoint'] = message["requests"]["temp_request"]
        self.status['temp_oda'] = message["unit"]['temp_oda']
        self.status['temp_ida'] = message["unit"]['temp_ida']
        self.status['temp_eha'] = message["unit"]['temp_eha']
        if self._max_flow:
            self.status['fan_mode'] = round( float(message["requests"]["fan_power_req"])/
                                            (float(self._max_flow)/100), -1
                                           )
            self.status['fan_eta_factor'] = round( float(message["unit"]["flow_eta"])/
                                            (float(self._max_flow)/100), -1
                                           )
            self.status['fan_sup_factor'] = round( float(message["unit"]["flow_sup"])/
                                            (float(self._max_flow)/100), -1
                                           )
        else:
            self.status['fan_eta_factor'] = message["unit"]['fan_eta_factor']
            self.status['fan_sup_factor'] = message["unit"]['fan_sup_factor']
            self.status['fan_mode'] = message["requests"]["fan_power_req"]

    async def send(self,message):
        # sends message and returns id you can look for in update
        msg = json.loads(message)
        msg['id'] = self._msg_id = self._msg_id + 1
        LOGGER.debug("MSG: %s" % msg)

        try:
            async with asyncio.timeout(TIMEOUT):
                await self._websocket.send(json.dumps(msg))
        except TimeoutError as err:
            LOGGER.debug("Connection to %s timed out", self._host)
            raise ConfigEntryNotReady from err

        return msg['id']

    async def login(self):
        LOGGER.debug("sending login to get token")
        msg_id = await self.send(
                    '{"endpoint":"login","args":{"username":"%s","password":"%s"}}'
                     % (self._username, self._password))
        token = await self.update(message_id = msg_id)
        LOGGER.debug("token is")
        await self.send('{"endpoint":"login","args":{"token":"%s"}}' % token)
        await self.ui_scheme()
        self.logged_in = True

    async def ui_scheme(self):
        response_id = await self.send('{ "endpoint": "ui_info_scheme", "args": null }')
        message = await self.update(response_id)
        if "flow_ventilation_req" in message["requests"]:
            response_id = await self.send('{ "endpoint": "ui_control_scheme", "args": null }')
            message = await self.update(response_id)
            self._max_flow = message["types"]["flow_ventilation_req"]["max"]
            self._min_flow = message["types"]["flow_ventilation_req"]["min"]

    async def on_close(self) -> None:
        # raise Exception("failed")
        LOGGER.info(f"RECONNECTING, {self.receive}, {self.on_close}")
        await self.ws_connect()

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self._websocket.connect(self.receive, self.on_close)

    async def set_fan_mode(self, fan_mode):
        if self._max_flow:
            flow_request = (float(self._max_flow)/100)*int(fan_mode)
            if flow_request < self._min_flow:
                flow_request = self._min_flow
            control = json.dumps({'variables': {"flow_ventilation_req": int(flow_request)}})
        else:
            control = json.dumps({'variables': {"fan_power_req": int(fan_mode)}})
        response_id = await self.send('{ "endpoint": "control", "args": %s }' % control)
        await self.update(response_id)

    def __init__(self, hass, host, username, password) -> None:
        """Initialize the Daikin Handle."""
        self._hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._available = True
        self.logged_in = False
        self._msg_id = 0
        self._messages = {}
        self._websocket = AtreaWebsocket(host)
        self._max_flow = None
        self._min_flow = None

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
          'temp_sup': None,
          'temp_eta': None,
          'season_current': None,
          'fan_eta_factor': None,
          'fan_sup_factor': None
        }
