"""Config flow for Amotion Atrea integration."""
from __future__ import annotations

import logging
import requests
import json
from typing import Any

import voluptuous as vol
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_USERNAME): str,
    }
)

from .const import (
    CONF_FAN_MODES,
    DOMAIN,
    LOGGER,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    DEFAULT_FAN_MODE_LIST,
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amotion Atrea."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                login_data = {'username': user_input[CONF_USERNAME], 'password': user_input[CONF_PASSWORD]}
                r = await self.hass.async_add_executor_job(requests.post, "http://%s/api/login" % user_input[CONF_HOST], json.dumps(login_data))
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

