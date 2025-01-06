import asyncio
import json
import websockets

from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER

class AtreaWebsocket:
    def __init__(self, host):
        self._host = host
        self._websocket = None
        self.reconnect_delay = 2
        self._failures = 0

    async def send(self, message):
        LOGGER.debug("Sending to ws %s", message)
        for i in range(120):
            if self._websocket:
                try:
                    await self._websocket.send(message)
                    return
                except websockets.exceptions.ConnectionClosed:
                    await asyncio.sleep(1)
                    i += 1
                    continue
        LOGGER.debug("Failed to send %s", message)
        self._websocket.close()

    async def handle_messages(self, websocket, on_data):
        try:
            async for message in websocket:
                LOGGER.debug("Received %s", message)
                try:
                    decoded_message = message.decode('utf-8') # Process decoded_message
                    await on_data(json.loads(decoded_message))
                except AttributeError:
                    await on_data(json.loads(message))
                except UnicodeDecodeError as e:
                    LOGGER.debug("Decoding error: %s", e)
        except websockets.exceptions.ConnectionClosedError as e:
            LOGGER.debug("Connection closed: %s", e)
            raise e

    async def connect(self, on_connect, on_data, on_close):
        try:
            async for websocket in websockets.connect(
                            f"ws://{self._host}/api/ws",
                            ping_interval=None,
                            ping_timeout=None,
                            logger=LOGGER):
                try:
                    self._websocket = websocket
                    if on_connect:
                        await on_connect()
                    await self.handle_messages(websocket, on_data)
                except websockets.exceptions.ConnectionClosed:
                    if on_close:
                        await on_close()
                    continue
        except Exception as err:
            LOGGER.debug("Unexpected error: %s", err)
            raise ConfigEntryNotReady from err
