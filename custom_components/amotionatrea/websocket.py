import asyncio
import json
import logging
import websockets

from homeassistant.exceptions import ConfigEntryNotReady

LOGGER = logging.getLogger(__name__)

class AtreaWebsocket:
    def __init__(self, url):
        self._url = url
        self._websocket = None
        self.reconnect_delay = 2

    async def send(self, message):
        LOGGER.debug("Sending to ws %s", message)
        for i in range(120):
            # Only attempt to send if the connection is active
            if not self._websocket:
                await asyncio.sleep(1)
                continue
            try:
                await self._websocket.send(message)
                return
            except websockets.exceptions.ConnectionClosed:
                # Handle the closed connection and retry
                await asyncio.sleep(1)
                continue
        LOGGER.debug("Failed to send %s", message)
        if self._websocket:
            self._websocket.close()

    async def handle_messages(self, websocket, on_data):
        try:
            async for message in websocket:
                LOGGER.debug("Received %s", message)
                try:
                    if isinstance(message, bytes):
                        decoded_message = message.decode('utf-8')
                    else:
                        decoded_message = message
                    await on_data(json.loads(decoded_message))
                except UnicodeDecodeError as e:
                    LOGGER.debug("Decoding error: %s", e)
        except websockets.exceptions.ConnectionClosedError as e:
            LOGGER.debug("Connection closed: %s", e)
            raise e

    async def connect(self, on_connect, on_data, on_close):
        LOGGER.info(f"{self._url}api/ws")
        try:
            async for websocket in websockets.connect(
                f"{self._url}api/ws",
                ping_interval=None,
                ping_timeout=None,
                logger=LOGGER
            ):
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
            LOGGER.exception("Unexpected error: %s", err)
            raise ConfigEntryNotReady from err
