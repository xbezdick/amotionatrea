import logging
from homeassistant.components.climate import (
    HVACMode,
    ClimateEntityFeature,
)

DOMAIN = "amotionatrea"

LOGGER = logging.getLogger(__name__)
TIMEOUT = 120

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
DEFAULT_FAN_MODE_LIST = "0,10,15,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100"
HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.HEAT_COOL,
]
