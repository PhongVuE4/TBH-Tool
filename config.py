"""
Centralized Configuration for Desktop Automation Tool (Supports config.json for EXE & Manual Editing).
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# Base paths (Support compiled PyInstaller EXE & script modes)
if getattr(sys, 'frozen', False):
    BASE_DIR: Path = Path(sys.executable).parent.resolve()
else:
    BASE_DIR: Path = Path(__file__).parent.resolve()

TEMPLATES_DIR: Path = BASE_DIR / "templates"
LOGS_DIR: Path = BASE_DIR / "logs"
CONFIG_JSON_PATH: Path = BASE_DIR / "config.json"

# Ensure required directories exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Default configuration template
DEFAULT_CONFIG = {
    "GAME_REGION": {
        "left": 1131,
        "top": 537,
        "width": 778,
        "height": 288
    },
    "INVENTORY_REGION": {
        "left": 1132,
        "top": 544,
        "width": 368,
        "height": 154
    },
    "CONFIDENCE_THRESHOLD": 0.85,
    "SCAN_INTERVAL": 0.25,
    "CLICK_DURATION": 0.02,
    "RANDOM_DELAY": [0.02, 0.06],
    "SALES_SLOTS_CAPACITY": 9,
    "CHECK_SYNTHESIS_TAB": True,
    "CHECK_UI_TABS": True,
    "UI_TAB_CHECK_INTERVAL": 12.0,
    "INVENTORY_SCROLL_ENABLED": True,
    "INVENTORY_SCROLL_MAX_STEPS": 5,
    "INVENTORY_SCROLL_TICKS": 6,
    "STASH_MODIFIER": "ctrl",
    "SELL_MODIFIER": "alt",
    "ITEM_MOUSE_BUTTON": "right",
    "FAILSAFE": True,
    "COOLDOWN_INTERVAL": 0.3,
    "VALIDATE_COORDINATES": True,
    "BACKGROUND_MODE": False,
    "LOG_ROTATION": "day",
    "LOG_RETENTION_DAYS": 14,
    "LANGUAGE": "vi",
    "HOTKEYS": {
        "START_PAUSE": "F1",
        "MEASURE_REGION": "F2",
        "QUICK_CAPTURE": "F3",
        "FREEZE_CAPTURE": "F4",
        "RELOAD_TEMPLATES": "F5",
        "EMERGENCY_STOP": "Esc"
    },
    "HOTKEY_FOCUS_PROCESSES": ["TaskBarHero"],
    "HOTKEY_FOCUS_TITLE_HINTS": ["Task Bar Hero", "TaskBarHero", "TBH:"]
}


def load_config_json() -> dict:
    """Loads configuration from config.json or creates default if missing."""
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.pop("SMART_MULTITASKING_MODE", None)
                merged = {**DEFAULT_CONFIG, **data}
                if "HOTKEYS" not in merged or not isinstance(merged["HOTKEYS"], dict):
                    merged["HOTKEYS"] = dict(DEFAULT_CONFIG["HOTKEYS"])
                else:
                    merged["HOTKEYS"] = {**DEFAULT_CONFIG["HOTKEYS"], **merged["HOTKEYS"]}
                if "HOTKEYS" not in data:
                    save_config_json(merged)
                return merged
        except Exception as e:
            print(f"[!] Warning reading config.json: {e}")

    save_config_json(DEFAULT_CONFIG)
    return DEFAULT_CONFIG


def save_config_json(config_data: dict) -> None:
    """Saves configuration dictionary to config.json on disk."""
    try:
        clean_data = {k: v for k, v in config_data.items() if k != "SMART_MULTITASKING_MODE"}
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=4)
    except Exception as e:
        print(f"[!] Error writing config.json: {e}")


# Initialize in-memory configuration
_cfg = load_config_json()

# Vision & Region Parameters
CONFIDENCE_THRESHOLD: float = float(_cfg.get("CONFIDENCE_THRESHOLD", 0.85))
MATCH_ALGORITHM: str = "TM_CCOEFF_NORMED"
GAME_REGION: Optional[Dict[str, int]] = _cfg.get("GAME_REGION")
INVENTORY_REGION: Optional[Dict[str, int]] = _cfg.get("INVENTORY_REGION")

# Automation Parameters
SCAN_INTERVAL: float = float(_cfg.get("SCAN_INTERVAL", 0.35))
CLICK_DURATION: float = float(_cfg.get("CLICK_DURATION", 0.18))
_raw_delay = _cfg.get("RANDOM_DELAY", [0.1, 0.25])
if isinstance(_raw_delay, (list, tuple)) and len(_raw_delay) >= 2:
    RANDOM_DELAY: Tuple[float, float] = (float(_raw_delay[0]), float(_raw_delay[1]))
else:
    RANDOM_DELAY: Tuple[float, float] = (0.1, 0.25)

# Action Key Combinations & Batch Rules
STASH_MODIFIER: str = str(_cfg.get("STASH_MODIFIER", "ctrl"))
SELL_MODIFIER: str = str(_cfg.get("SELL_MODIFIER", "alt"))
ITEM_MOUSE_BUTTON: str = str(_cfg.get("ITEM_MOUSE_BUTTON", "right"))
SALES_SLOTS_CAPACITY: int = int(_cfg.get("SALES_SLOTS_CAPACITY", 9))
HOTKEYS: Dict[str, str] = _cfg.get("HOTKEYS", DEFAULT_CONFIG["HOTKEYS"])

# Template Sub-directories
SELL_ITEMS_DIR: Path = TEMPLATES_DIR / "sell_items"
STASH_ITEMS_DIR: Path = TEMPLATES_DIR / "stash_items"
CHESTS_DIR: Path = TEMPLATES_DIR / "chests"
CUBE_DIR: Path = TEMPLATES_DIR / "cube"
UI_DIR: Path = TEMPLATES_DIR / "ui"

SELL_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
STASH_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
CHESTS_DIR.mkdir(parents=True, exist_ok=True)
CUBE_DIR.mkdir(parents=True, exist_ok=True)
UI_DIR.mkdir(parents=True, exist_ok=True)

# Application Safety Flag
FAILSAFE: bool = bool(_cfg.get("FAILSAFE", True))
INVENTORY_SCROLL_ENABLED: bool = bool(_cfg.get("INVENTORY_SCROLL_ENABLED", True))
INVENTORY_SCROLL_MAX_STEPS: int = int(_cfg.get("INVENTORY_SCROLL_MAX_STEPS", 5))
INVENTORY_SCROLL_TICKS: int = int(_cfg.get("INVENTORY_SCROLL_TICKS", 6))
LOG_RETENTION_DAYS: int = int(_cfg.get("LOG_RETENTION_DAYS", 14))
LOG_LEVEL: str = str(_cfg.get("LOG_LEVEL", "INFO"))
COOLDOWN_INTERVAL: float = float(_cfg.get("COOLDOWN_INTERVAL", 0.3))
CHECK_SYNTHESIS_TAB: bool = bool(_cfg.get("CHECK_SYNTHESIS_TAB", True))


CHECK_UI_TABS: bool = bool(_cfg.get("CHECK_UI_TABS", True))
UI_TAB_CHECK_INTERVAL: float = float(_cfg.get("UI_TAB_CHECK_INTERVAL", 12.0))
VALIDATE_COORDINATES: bool = bool(_cfg.get("VALIDATE_COORDINATES", True))
BACKGROUND_MODE: bool = bool(_cfg.get("BACKGROUND_MODE", False))


def _as_str_list(value, fallback) -> list:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(fallback)


HOTKEY_FOCUS_PROCESSES = _as_str_list(
    _cfg.get("HOTKEY_FOCUS_PROCESSES"),
    DEFAULT_CONFIG["HOTKEY_FOCUS_PROCESSES"],
)
HOTKEY_FOCUS_TITLE_HINTS = _as_str_list(
    _cfg.get("HOTKEY_FOCUS_TITLE_HINTS"),
    DEFAULT_CONFIG["HOTKEY_FOCUS_TITLE_HINTS"],
)



def update_region(region_name: str, left: int, top: int, width: int, height: int) -> None:
    """Updates region coordinates in config.json and in memory."""
    global GAME_REGION, INVENTORY_REGION
    region_dict = {"left": left, "top": top, "width": width, "height": height}
    _cfg[region_name] = region_dict
    save_config_json(_cfg)

    if region_name == "GAME_REGION":
        GAME_REGION = region_dict
    elif region_name == "INVENTORY_REGION":
        INVENTORY_REGION = region_dict


def update_setting(key: str, value) -> None:
    """Dynamically updates a configuration key in memory and saves to config.json."""
    global CONFIDENCE_THRESHOLD, SCAN_INTERVAL, CLICK_DURATION, RANDOM_DELAY, COOLDOWN_INTERVAL, SALES_SLOTS_CAPACITY, STASH_MODIFIER, SELL_MODIFIER
    global ITEM_MOUSE_BUTTON, FAILSAFE, INVENTORY_SCROLL_ENABLED, INVENTORY_SCROLL_MAX_STEPS, INVENTORY_SCROLL_TICKS, HOTKEYS

    _cfg[key] = value
    save_config_json(_cfg)

    if key == "CONFIDENCE_THRESHOLD":
        CONFIDENCE_THRESHOLD = float(value)
    elif key == "SCAN_INTERVAL":
        SCAN_INTERVAL = float(value)
    elif key == "CLICK_DURATION":
        CLICK_DURATION = float(value)
    elif key == "RANDOM_DELAY":
        RANDOM_DELAY = [float(value[0]), float(value[1])]
    elif key == "COOLDOWN_INTERVAL":
        COOLDOWN_INTERVAL = float(value)
    elif key == "SALES_SLOTS_CAPACITY":
        SALES_SLOTS_CAPACITY = int(value)
    elif key == "STASH_MODIFIER":
        STASH_MODIFIER = str(value)
    elif key == "SELL_MODIFIER":
        SELL_MODIFIER = str(value)
    elif key == "ITEM_MOUSE_BUTTON":
        ITEM_MOUSE_BUTTON = str(value)
    elif key == "FAILSAFE":
        FAILSAFE = bool(value)
    elif key == "INVENTORY_SCROLL_ENABLED":
        INVENTORY_SCROLL_ENABLED = bool(value)
    elif key == "INVENTORY_SCROLL_MAX_STEPS":
        INVENTORY_SCROLL_MAX_STEPS = int(value)
    elif key == "INVENTORY_SCROLL_TICKS":
        INVENTORY_SCROLL_TICKS = int(value)
    elif key == "HOTKEYS" and isinstance(value, dict):
        HOTKEYS = value
