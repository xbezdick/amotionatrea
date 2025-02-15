import logging
from homeassistant.components.climate.const import (
    HVACMode,
    HVACAction,
    HVACMode,
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)

DOMAIN = "amotionatrea"
CONF_HOST = "host"

LOGGER = logging.getLogger(__name__)
TIMEOUT = 120

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
DEFAULT_NAME = "Atrea"
STATE_MANUAL = "manual"
STATE_UNKNOWN = "unknown"
CONF_FAN_MODES = "fan_modes"
CONF_PRESETS = "presets"
DEFAULT_FAN_MODE_LIST = "12,20,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100"
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

HVAC_MODES = [HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACAction.IDLE,
    HVACAction.HEATING,
    HVACAction.COOLING,
    ]
