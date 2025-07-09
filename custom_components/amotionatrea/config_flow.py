from __future__ import annotations

import logging
import json
from typing import Any

import voluptuous as vol
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_URL,
    CONF_PASSWORD,
    CONF_USERNAME,
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
from .const import (
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_URL,
            description={"suggested_value": "ws://192.168.1.100:8080"},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(
            CONF_USERNAME,
        ): str,
        vol.Required(
            CONF_PASSWORD,
        ): str,
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
            host = config_entry.data[CONF_HOST]
            if not host.startswith("ws://") and not host.startswith("wss://"):
                host = "ws://" + host
            new_data = {
                CONF_URL: host,
                CONF_USERNAME: config_entry.data[CONF_USERNAME],
                CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
                CONF_NAME: config_entry.data[CONF_NAME],
            }
            hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of the config flow."""
        #if self._async_current_entries():
        #    return self.async_abort(reason="single_instance_allowed")

        user_input = user_input or {}
        self.url = user_input.get(CONF_URL, self.url)
        self.name = user_input.get(CONF_NAME, self.name)
        self.username = user_input.get(CONF_USERNAME, self.username)
        self.password = user_input.get(CONF_PASSWORD, self.password)

        errors: dict[str, str] = {}

        # Validate URL format immediately
        if not self.url:
            errors["url"] = "required"
        elif not (self.url.startswith("ws://") or self.url.startswith("wss://")):
            errors["url"] = "invalid_url_format"

        # If no URL errors, proceed to check connection
        if not errors:
            try:
                self.atrea = AmotionAtrea(
                    hass=self.hass,
                    url=self.url,
                    username=self.username,
                    password=self.password
                )
                await self.atrea.fetch()
                LOGGER.info("LOGGED")
                if not self.atrea.logged_in:
                    errors["base"] = "invalid_auth"
            except (UpdateFailed, ConfigEntryNotReady) as e:
                # Check for unauthorized error message in exception
                if "UNAUTHORIZED" in str(e):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception as e:
                LOGGER.exception("Unexpected error during login: %s", e)
                errors["base"] = "unknown"

        # Show the form again with errors if any
        if errors:
            if self.atrea:
                del(self.atrea)
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors
            )

        # Handle optional name field (if not provided earlier)
        if self.name is None:
            name_step_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        description={"suggested_value": self.atrea.name},
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
