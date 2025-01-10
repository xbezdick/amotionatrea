import logging
from homeassistant.components.climate.const import (
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_FAN_MODE,

)

DOMAIN = "amotionatrea"
CONF_HOST = "host"

LOGGER = logging.getLogger(__name__)
TIMEOUT = 120

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE
DEFAULT_NAME = "Atrea"
STATE_MANUAL = "manual"
STATE_UNKNOWN = "unknown"
CONF_FAN_MODES = "fan_modes"
CONF_PRESETS = "presets"
DEFAULT_FAN_MODE_LIST = "12,20,30,40,50,60,70,80,90,100"
ALL_PRESET_LIST = [
    "Off",
    "Automatic",
    "Ventilation",
    "Circulation and Ventilation",
    "Circulation",
    "Night precooling",
    "Disbalance",
    "Overpressure",
    "Periodic ventilation",
    "Startup",
    "Rundown",
    "Defrosting",
    "External",
    "HP defrosting",
    "IN1",
    "IN2",
    "D1",
    "D2",
    "D3",
    "D4",
]

HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_COOL]
