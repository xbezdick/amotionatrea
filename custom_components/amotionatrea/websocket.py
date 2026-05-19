"""WebSocket client for Amotion Atrea devices."""

import asyncio
import json
import logging
from typing import Any, Callable

import websockets

from homeassistant.exceptions import ConfigEntryNotReady

from .const import RECONNECT_DELAY, MAX_SEND_RETRIES

LOGGER = logging.getLogger(__name__)


class AtreaWebsocket:
    """WebSocket client for Amotion Atrea devices."""

    def __init__(self, url: str) -> None:
        """Initialize the WebSocket client.

        Args:
            url: The base URL of the Atrea device.
        """
        self._url: str = url
        self._websocket: Any = None
        self.reconnect_delay: int = RECONNECT_DELAY

    async def send(self, message: str) -> None:
        """Send a message via WebSocket.

        Args:
            message: The JSON message to send.

        Raises:
            TimeoutError: If unable to send after maximum retries.
        """
        LOGGER.debug("Sending to ws %s", message)
        for attempt in range(MAX_SEND_RETRIES):
            # Only attempt to send if the connection is active
            if not self._websocket:
                # Exponential backoff: 1s, 2s, 4s, ... up to 30s
                delay = min(2 ** attempt, 30)
                await asyncio.sleep(delay)
                continue
            try:
                await self._websocket.send(message)
                return
            except websockets.exceptions.ConnectionClosed:
                # Handle the closed connection and retry with backoff
                delay = min(2 ** attempt, 30)
                await asyncio.sleep(delay)
                continue
        LOGGER.debug("Failed to send %s", message)
        if self._websocket:
            await self._websocket.close()

    async def handle_messages(
        self,
        websocket: Any,
        on_data: Callable[[dict[str, Any]], Any]
    ) -> None:
        """Handle incoming WebSocket messages.
            on_data: Callback function to process received data.

        Raises:
            websockets.exceptions.ConnectionClosedError: If connection is closed unexpectedly.
        """
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

    async def connect(
        self,
        on_connect: Callable[[], Any],
        on_data: Callable[[dict[str, Any]], Any],
        on_close: Callable[[], Any]
    ) -> None:
        """Connect to the WebSocket server.

        Args:
            on_connect: Callback when connection is established.
            on_data: Callback for incoming messages.
            on_close: Callback when connection is closed.
        """
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
