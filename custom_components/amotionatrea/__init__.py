import requests
import json

from .const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True
