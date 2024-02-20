import requests
import json

from .const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """ Setup connection to atrea """
    session = requests.Session()
    try:
        login_data = {'username': entry.data[CONF_USERNAME], 'password': entry.data[CONF_PASSWORD]}
        r = await hass.async_add_executor_job(session.post, "http://%s/api/login" % entry.data[CONF_HOST], json.dumps(login_data))
        session.headers.update({'X-ATC-TOKEN': r.json()['result']})
    except Exception as e:
        raise ConfigEntryNotReady from e
    hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "climate")

    return True
