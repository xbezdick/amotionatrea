""" Module providing home assistant integration for Amotion Atrea Devices """

import json
import logging
import asyncio
from datetime import timedelta, datetime

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
)
from .websocket import AtreaWebsocket

LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup connection to atrea."""
    try:
        atrea = AmotionAtrea(hass,
                             entry.data[CONF_URL],
                             entry.data[CONF_USERNAME],
                             entry.data[CONF_PASSWORD])
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
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(TIMEOUT):
                return await self.aatrea.fetch()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class AmotionAtrea:
    """Keep the AmotionAtrea instance in one place and centralize websocket use."""

    async def on_close(self) -> None:
        LOGGER.debug("Reset counter")
        self._msg_id = 0

    async def on_connect(self):
        LOGGER.debug("Connected")
        self._hass.async_create_background_task(
            self.login(), "amotionatrea-login"
        )

    async def receive(self, message):
        """ Sample responses we get:
        {'args': {'active': False, 'countdown': 0, 'finish': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}, 'sceneId': 0, 'start': {'day': 0, 'hour': 0, 'minute': 0, 'month': 0, 'year': 0}}, 'event': 'disposable_plan', 'type': 'event'} #pylint: disable=line-too-long
        {'code': 'OK', 'error': None, 'id': None, 'response': {'ui_diagram_data': {'bypass_estim': 100, 'damper_io_state': True, 'fan_eta_operating_time': 24, 'fan_sup_operating_time': 24, 'preheater_active': False, 'preheater_factor': 0, 'preheater_type': 'ELECTRO_PWM'}}, 'type': 'response'} #pylint: disable=line-too-long
        {'code': 'OK', 'error': None, 'id': 4, 'response': {'requests': {'fan_power_req': 60, 'temp_request': 22.0, 'work_regime': 'VENTILATION'}, 'states': {'active': {}}, 'unit': {'fan_eta_factor': 60, 'fan_sup_factor': 60, 'mode_current': 'NORMAL', 'season_current': 'NON_HEATING', 'temp_eha': 23.0, 'temp_eta': 23.0, 'temp_ida': 23.0, 'temp_oda': 16.2, 'temp_oda_mean': 16.275, 'temp_sup': 17.5}}, 'type': 'response'} #pylint: disable=line-too-long
        {'args': {'requests': {'fan_power_req': 30, 'temp_request': 18.5, 'work_regime': 'VENTILATION'}, 'states': {'active': {}}, 'unit': {'fan_eta_factor': 30, 'fan_sup_factor': 30, 'mode_current': 'NORMAL', 'season_current': 'NON_HEATING', 'temp_eha': 23.9, 'temp_eta': 23.9, 'temp_ida': 23.9, 'temp_oda': 22.9, 'temp_oda_mean': 22.25, 'temp_sup': 23.3}}, 'event': 'ui_info', 'type': 'event'} #pylint: disable=line-too-long
        {"code":"UNAUTHORIZED","error":"Unauthorized: No authorized user (or missing token)","id":9,"response":null,"type":"response"} #pylint: disable=line-too-long
        """
        LOGGER.debug("receive message: %s", message)
        if 'id' in message and message['id']:
            if message['code'] == 'UNAUTHORIZED':
                LOGGER.debug("BORK")
                raise ConfigEntryNotReady("UNAUTHORIZED")
            self._messages[message['id']] = message['response']
            LOGGER.debug("Stored messages: %s", self._messages)
        elif message['type'] == 'event' and message['event'] == 'ui_info' and self.logged_in:
            await self._update_status(message)

    async def _update_status(self, message):
        self.status['current_temperature'] = message["args"]["unit"]["temp_sup"]
        self.status['setpoint'] = message["args"]["requests"]["temp_request"]
        self.status['temp_oda'] = message["args"]["unit"]['temp_oda']
        self.status['temp_ida'] = message["args"]["unit"]['temp_ida']
        self.status['temp_eha'] = message["args"]["unit"]['temp_eha']
        self.status['temp_eta'] = message["args"]["unit"]['temp_eta']
        self.status['temp_sup'] = message["args"]["unit"]['temp_sup']
        self.status['season_current'] = message["args"]["unit"]['season_current']
        self.status['last_update'] = datetime.now()

        if self._max_flow:
            self.status['fan_mode'] = round(
                float(message["args"]["requests"]["flow_ventilation_req"]) /
                (float(self._max_flow) / 100), -1
            )
            self.status['fan_eta_factor'] = round(
                float(message["args"]["unit"]["flow_eta"]) /
                (float(self._max_flow) / 100), -1
            )
            self.status['fan_sup_factor'] = round(
                float(message["args"]["unit"]["flow_sup"]) /
                (float(self._max_flow) / 100), -1
            )
        else:
            self.status['fan_eta_factor'] = message["args"]["unit"]['fan_eta_factor']
            self.status['fan_sup_factor'] = message["args"]["unit"]['fan_sup_factor']
            self.status['fan_mode'] = message["args"]["requests"]["fan_power_req"]

    async def update(self, message_id=None):
        LOGGER.debug("update %s", message_id)
        if message_id:
            try:
                async with asyncio.timeout(30):
                    for i in range(30):
                        if message_id in self._messages:
                            msg = self._messages[message_id]
                            del self._messages[message_id]
                            LOGGER.debug("Found message %s", msg)
                            return msg
                        await asyncio.sleep(1)
            except asyncio.TimeoutError:
                LOGGER.debug("Timeout while waiting for message_id: %s", message_id)

    async def fetch(self):
        if self._max_flow:
            await self.time()
        LOGGER.debug(self.status['last_update'])

        if self.status['current_temperature'] is None or (
            datetime.now() - self.status['last_update'] >= timedelta(minutes=2)
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
                # mingle the message to use single function to update status
                message["args"] = message
                await self._update_status(message)
        # Get maintenance data and ui_diagram_data every 5 minutes
        if datetime.now() - self.status['last_maintenance_update'] >= timedelta(minutes=5):
            await self.async_get_maintenance_data()
            await self.async_get_diagram_data()

    async def send(self, message):
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


    async def async_get_discovery(self):
        response_id = await self.send('{"endpoint": "discovery", "args": null}')
        discovery_data = await self.update(response_id)
        # Sample data:
        # {'activation_status': 'READY', 'addresses': {'eth0': ['172.20.20.20', '192.168.0.11']}, 'board_number': '0c:2g:b3:0d:11:0a', 'board_type': 'CL', 'brand': 'atrea.cz', 'cloud': {'enable': False, 'link': 'https://amotion.cloud', 'support': True}, 'commissioned': False, 'initialized': True, 'localisation': 'cs', 'name': 'DUPLEX 380 ECV5.aM-CL', 'port': 80, 'production_number': 'FFFFFFF', 'service_name': '', 'type': 'DUPLEX 380 ECV5.aM-CL', 'version': 'ATC-v2.3.0'} #pylint: disable=line-too-long
        if discovery_data:
            self.model = discovery_data.get('type', 'Unknown')
            self.serial = discovery_data.get('production_number', 'Unknown')
            self.brand = discovery_data.get('brand', 'Atrea')
            self.name = discovery_data.get('name', 'Atrea')

    async def async_get_version(self):
        response_id = await self.send('{"endpoint": "version", "args": null}')
        version_data = await self.update(response_id)
        if version_data:
            controller_info = version_data.get('CONTROLLER', {})
            self.sw_version = controller_info.get('version', 'Unknown')

    async def login(self):
        LOGGER.debug("Sending login to get token")
        msg_id = await self.send(
            f'{{"endpoint":"login","args":' \
            f'{{"username":"{self._username}","password":"{self._password}"}}}}'
        )
        token = await self.update(message_id=msg_id)
        LOGGER.debug("Token is %s", token)
        await self.send(f'{{"endpoint":"login","args":{{"token":"{token}"}}}}')
        await self.ui_scheme()
        self.logged_in = True

        await self.async_get_discovery()
        await self.async_get_version()

    async def ui_scheme(self):
        response_id = await self.send('{"endpoint": "ui_info_scheme", "args": null}')
        message = await self.update(response_id)
        response_id = await self.send('{"endpoint": "ui_control_scheme", "args": null}')
        self.control_scheme = await self.update(response_id)
        if "flow_ventilation_req" in message["requests"]:
            self._max_flow = self.control_scheme["types"]["flow_ventilation_req"]["max"]
            self._min_flow = self.control_scheme["types"]["flow_ventilation_req"]["min"]

    async def async_get_diagram_data(self):
        """Fetch diagram data including bypass_estim from the server."""
        response_id = await self.send('{"endpoint": "ui_diagram_data", "args": null}')
        diagram_response = await self.update(response_id)
        if diagram_response:
            # The server returns `ui_diagram_data` as a nested key in the response
            ui_diagram = diagram_response.get("ui_diagram_data", {})
            self.status['bypass_estim'] = ui_diagram.get("bypass_estim", 0)
            self.status['preheater_factor'] = ui_diagram.get("preheater_factor", 0)

    async def async_get_maintenance_data(self):
        """ Get maintenance information like filter change dates and motor hours """
        response_id = await self.send('{"endpoint": "moments/get", "args": null}')
        moment_data = await self.update(response_id)
        self.status['last_maintenance_update'] = datetime.now()
        self.status['filters_last_change'] = moment_data.get('lastFilterReset', {})
        self.status['inspection_date'] = moment_data.get('inspection', {})

        self.status['motor1_hours'] = round(moment_data['m1_register'] / 3600)
        self.status['motor2_hours'] = round(moment_data['m2_register'] / 3600)
        # UV lamp operating hours
        if 'uv_lamp_register' in moment_data and moment_data['uv_lamp_register'] > 0:
            self.status['uv_lamp_hours'] = round(moment_data['uv_lamp_register'] / 3600)
            self.has_uv_lamp = True
        else:
            self.status['uv_lamp_hours'] = None
            self.has_uv_lamp = False

    async def time(self):
        response_id = await self.send('{"endpoint":"time", "args": null}')
        message = await self.update(response_id)
        LOGGER.debug("TIME %s", message)

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self._websocket.connect(self.on_connect, self.receive, self.on_close)

    async def set_fan_mode(self, fan_mode):
        if self._max_flow:
            flow_request = (float(self._max_flow) / 100) * int(fan_mode)
            flow_request = max(flow_request, self._min_flow)
            control = json.dumps({'variables': {"flow_ventilation_req": int(flow_request)}})
        else:
            control = json.dumps({'variables': {"fan_power_req": int(fan_mode)}})
        response_id = await self.send(f'{{ "endpoint": "control", "args": {control} }}')
        await self.update(response_id)

    async def set_temperature(self, temperature):
        control = json.dumps({'variables': {'temp_request': int(temperature)}})
        response_id = await self.send('{ "endpoint": "control", "args": %s }' % control)
        await self.update(response_id)

    async def set_hvac_mode(self, hvac_mode):
        """
        FIXME this should be setting based on UI control scheme
        """
        mode = 'OFF'
        match hvac_mode:
            case HVACMode.HEAT_COOL:
                mode = 'VENTILATION'
            case HVACMode.AUTO:
                mode = 'AUTO'
        control = json.dumps({'variables': {"work_regime": mode}})
        response_id = await self.send('{ "endpoint": "control", "args": %s }' % control)
        await self.update(response_id)

    def __init__(
        self,
        hass,
        url: str,
        username: str,
        password: str
    ) -> None:
        self._hass = hass
        self._url = url
        self._username = username
        self._password = password

        self._available = True
        self.logged_in = False
        self._msg_id = 0
        self._messages = {}
        self._websocket = AtreaWebsocket(url)
        self._max_flow = None
        self._min_flow = None
        self.control_scheme = {}
        self.has_uv_lamp = False

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

        self.model = None
        self.sw_version = None
        self.serial = None
        self.brand = "Atrea"
        self.name = "Atrea"

        self._hass.async_create_background_task(
            self.ws_connect(), "amotionatrea-ws_connect"
        )
