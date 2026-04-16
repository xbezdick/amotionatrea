"""Constants for the Amotion Atrea integration."""

from homeassistant.components.climate import (
    HVACMode,
    ClimateEntityFeature,
)

# Domain and basic configuration
DOMAIN: str = "amotionatrea"
TIMEOUT: int = 120
RECONNECT_DELAY: int = 2
MAX_SEND_RETRIES: int = 120

# Background task names (prevents hardcoded strings)
BACKGROUND_TASK_LOGIN: str = "amotionatrea-login"
BACKGROUND_TASK_WS_CONNECT: str = "amotionatrea-ws_connect"

# Climate entity features
SUPPORT_FLAGS: ClimateEntityFeature = (
    ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
)

# Fan modes (0-100 in steps of 5)
DEFAULT_FAN_MODE_LIST: list[str] = [
    "0", "5", "10", "15", "20", "25", "30",
    "35", "40", "45", "50", "55", "60",
    "65", "70", "75", "80", "85", "90",
    "95", "100",
]

# HVAC modes supported by the device
HVAC_MODES: list[HVACMode] = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.HEAT_COOL,
]

SUPPORT_FLAGS = (
    ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.TARGET_TEMPERATURE
)

DEFAULT_FAN_MODE_LIST = ["0","5","10","15","20","25","30",
                         "35","40","45","50","55","60",
                         "65","70","75","80","85","90",
                         "95","100"]
HVAC_MODES = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.HEAT_COOL,
]
