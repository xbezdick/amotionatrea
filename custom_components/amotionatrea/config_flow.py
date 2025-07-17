from __future__ import annotations

import logging
from urllib.parse import urlparse
import asyncio

import voluptuous as vol
from homeassistant.const import (
    CONF_NAME,
    CONF_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import AmotionAtrea  # Import the custom class from __init__.py
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_URL,
            description={"suggested_value": "ws://192.168.1.100:8080"},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amotion Atrea integration."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self.url: str | None = None
        self.name: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.atrea: AmotionAtrea | None = None

    async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
        """Migrate old entry."""
        LOGGER.info("Migrating configuration from version %s.%s", config_entry.version, config_entry.minor_version)

        if config_entry.version == 1:
            host = config_entry.data.get(CONF_HOST)
            if not host or not (host.startswith("ws://") or host.startswith("wss://")):
                if host and not host.startswith("ws://"):
                    host = "ws://" + host
                else:
                    # If no host was present, use default
                    host = "ws://192.168.1.100:8080"
            new_data = {
                CONF_URL: host,
                CONF_USERNAME: config_entry.data[CONF_USERNAME],
                CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
                CONF_NAME: config_entry.data.get(CONF_NAME, "Amotion Atrea"),
            }
            hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of the config flow."""
        # Prevent multiple entries if this is a singleton integration
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        user_input = user_input or {}
        self.url = user_input.get(CONF_URL, self.url)
        self.username = user_input.get(CONF_USERNAME, self.username)
        self.password = user_input.get(CONF_PASSWORD, self.password)

        errors: dict[str, str] = {}

        # Validate URL has correct protocol
        if not self.url:
            errors["url"] = "required"
        elif not (self.url.startswith("ws://") or self.url.startswith("wss://")):
            errors["url"] = "invalid_url_format"

        # Parse to extract host and port for connectivity check
        parsed_url = urlparse(self.url)
        host = parsed_url.hostname

        if host is None:
            errors["url"] = "invalid_url_format"
        else:
            scheme = parsed_url.scheme
            if scheme == 'ws':
                port = parsed_url.port or 80
            elif scheme == 'wss':
                port = parsed_url.port or 443
            else:
                # This shouldn't happen since we've already validated protocol
                errors["base"] = "unknown"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors
                )

            try:
                async with asyncio.timeout(10):
                    reader, writer = await asyncio.open_connection(host, port)
                    writer.close()
                    await writer.wait_closed()
            except Exception as e:
                LOGGER.debug("Could not connect to %s:%s", host, port, exc_info=True)
                errors["base"] = "cannot_connect"


        # Now validate login
        if not errors:
            # Ensure URL ends with a slash
            if not self.url.endswith("/"):
                self.url += "/"
            try:
                self.atrea = AmotionAtrea(
                    hass=self.hass,
                    url=self.url,
                    username=self.username,
                    password=self.password
                )
                await self.atrea.fetch()
                if not self.atrea.logged_in:
                    errors["base"] = "invalid_auth"
            except (UpdateFailed, ConfigEntryNotReady) as e:
                # Handle specific unauthorized error message
                if "UNAUTHORIZED" in str(e):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                LOGGER.exception("Unexpected error during login: %s", e)
                errors["base"] = "unknown"

        # Show form again with errors
        if errors:
            if self.atrea:
                del self.atrea  # Clean up before retrying
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors
            )

        # Handle optional name field
        if self.name is None:
            suggested_name = self.atrea.name if self.atrea else "Amotion Atrea"
            name_step_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        description={"suggested_value": suggested_name},
                    ): str,
                }
            )
            return self.async_show_form(
                step_id="user",
                data_schema=name_step_schema
            )

        return self.async_create_entry(
            title=f"{self.name}",
            data={
                CONF_URL: self.url,
                CONF_USERNAME: self.username,
                CONF_PASSWORD: self.password,
                CONF_NAME: user_input.get(CONF_NAME, self.name),
            },
        )

