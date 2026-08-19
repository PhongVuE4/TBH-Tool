"""
Automation Engine: Native Win32 hardware key events (VK_LMENU, VK_LCONTROL), sales capacity checking, chest opening, Cube Alchemy mode switcher, and inventory scrolling.
"""

import ctypes
import random
import time
from threading import Event
from typing import Dict, Optional, Tuple
import pyautogui

import config
from utils import logger
from vision import MatchResult

# Configure PyAutoGUI Failsafe & Timings
pyautogui.FAILSAFE = config.FAILSAFE
pyautogui.PAUSE = 0.05

# Win32 Virtual Key & Scan Codes (Bypasses Windows System Menu Interception)
VK_LCONTROL = 0xA2  # Left Ctrl
VK_LMENU = 0xA4     # Left Alt
KEYEVENTF_KEYUP = 0x0002


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def win32_key_down(key_name: str) -> None:
    """Sends native hardware KeyDown event for Alt/Ctrl using Win32 API."""
    key = key_name.lower()
    if key in ("alt", "altleft", "lalt"):
        ctypes.windll.user32.keybd_event(VK_LMENU, 0x38, 0, 0)
    elif key in ("ctrl", "ctrlleft", "lctrl"):
        ctypes.windll.user32.keybd_event(VK_LCONTROL, 0x1D, 0, 0)
    else:
        pyautogui.keyDown(key_name)


def win32_key_up(key_name: str) -> None:
    """Sends native hardware KeyUp event for Alt/Ctrl using Win32 API."""
    key = key_name.lower()
    if key in ("alt", "altleft", "lalt"):
        ctypes.windll.user32.keybd_event(VK_LMENU, 0x38, KEYEVENTF_KEYUP, 0)
    elif key in ("ctrl", "ctrlleft", "lctrl"):
        ctypes.windll.user32.keybd_event(VK_LCONTROL, 0x1D, KEYEVENTF_KEYUP, 0)
    else:
        pyautogui.keyUp(key_name)


def send_win32_bg_click(x: int, y: int, button: str = "right", modifier: Optional[str] = None) -> bool:
    """Sends native Win32 PostMessage mouse click to target window handle WITHOUT moving the hardware cursor."""
    user32 = ctypes.windll.user32
    pt = POINT(x, y)
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return False
    root_hwnd = user32.GetAncestor(hwnd, 2)  # GA_ROOT = 2
    target_hwnd = root_hwnd if root_hwnd else hwnd

    client_pt = POINT(x, y)
    user32.ScreenToClient(target_hwnd, ctypes.byref(client_pt))
    cx, cy = client_pt.x, client_pt.y
    lparam = (cy << 16) | (cx & 0xFFFF)

    wparam = 0
    if modifier:
        mod_key = modifier.lower()
        if "ctrl" in mod_key:
            wparam |= 0x0008  # MK_CONTROL
            user32.PostMessageW(target_hwnd, 0x0100, 0x11, 0)  # WM_KEYDOWN VK_CONTROL
        elif "alt" in mod_key:
            wparam |= 0x0020  # MK_ALT
            user32.PostMessageW(target_hwnd, 0x0100, 0x12, 0)  # WM_KEYDOWN VK_MENU

    if button == "right":
        wparam |= 0x0002  # MK_RBUTTON
        user32.PostMessageW(target_hwnd, 0x0204, wparam, lparam)  # WM_RBUTTONDOWN
        time.sleep(0.04)
        user32.PostMessageW(target_hwnd, 0x0205, 0, lparam)       # WM_RBUTTONUP
    else:
        wparam |= 0x0001  # MK_LBUTTON
        user32.PostMessageW(target_hwnd, 0x0201, wparam, lparam)  # WM_LBUTTONDOWN
        time.sleep(0.04)
        user32.PostMessageW(target_hwnd, 0x0202, 0, lparam)       # WM_LBUTTONUP

    if modifier:
        mod_key = modifier.lower()
        if "ctrl" in mod_key:
            user32.PostMessageW(target_hwnd, 0x0101, 0x11, 0)  # WM_KEYUP VK_CONTROL
        elif "alt" in mod_key:
            user32.PostMessageW(target_hwnd, 0x0101, 0x12, 0)  # WM_KEYUP VK_MENU

    return True


class AutomationEngine:
    """Handles mouse/keyboard execution with modifier keys and batch sales rules."""

    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_action_time: Dict[str, float] = {}
        self.current_sales_slots: int = 0  # Number of slots filled in sales section
        # Set by the worker as soon as pause/stop is requested.  Input helpers
        # consult it immediately, so a previously detected match cannot click.
        self._interrupt_event = Event()
        
        # Sanitize OS modifier keys at startup to clear sticky keys
        self.sanitize_modifier_keys()
        
        logger.info(
            f"TBH-Tool Automation Engine initialized (PVandAI). "
            f"Screen Bounds: {self.screen_width}x{self.screen_height}px. "
            f"FailSafe={config.FAILSAFE}"
        )

    def sanitize_modifier_keys(self) -> None:
        """Forces release of all keyboard modifier keys (ctrl, alt, shift) via Win32 API."""
        win32_key_up("alt")
        win32_key_up("ctrl")
        pyautogui.keyUp("shift")

    def set_interrupted(self, interrupted: bool) -> None:
        """Enable/disable immediate cancellation of queued input actions."""
        if interrupted:
            self._interrupt_event.set()
            self.sanitize_modifier_keys()
        else:
            self._interrupt_event.clear()

    def is_interrupted(self) -> bool:
        return self._interrupt_event.is_set()

    def wait(self, seconds: float) -> bool:
        """Wait until *seconds* elapse; return False if pause/stop interrupts it."""
        return not self._interrupt_event.wait(max(0.0, seconds))

    def prime_input_hooks(self) -> None:
        """Primes Windows DirectInput keyboard hooks before main loop execution."""
        self.sanitize_modifier_keys()
        win32_key_down("alt")
        time.sleep(0.08)
        win32_key_up("alt")
        time.sleep(0.05)
        win32_key_down("ctrl")
        time.sleep(0.08)
        win32_key_up("ctrl")
        self.sanitize_modifier_keys()

    def validate_coordinates(self, x: int, y: int) -> bool:
        """Validates that coordinates are within display boundaries."""
        if not config.VALIDATE_COORDINATES:
            return True
        valid = 0 <= x < self.screen_width and 0 <= y < self.screen_height
        if not valid:
            logger.error(f"Coordinates ({x}, {y}) out of screen bounds ({self.screen_width}x{self.screen_height})!")
        return valid

    def is_in_cooldown(self, action_key: str, cooldown_seconds: float = config.COOLDOWN_INTERVAL) -> bool:
        """Checks if a specific template action location is in cooldown to prevent duplicate clicks."""
        now = time.time()
        last = self.last_action_time.get(action_key, 0.0)
        if now - last < cooldown_seconds:
            return True
        return False

    def _move_and_click(
        self,
        x: int,
        y: int,
        button: str = "right",
        modifier: Optional[str] = None,
        click_duration: float = config.CLICK_DURATION,
    ) -> bool:
        """Helper to execute mouse movement and click with Win32 hardware modifier events."""
        if self.is_interrupted() or not self.validate_coordinates(x, y):
            return False

        try:
            self.sanitize_modifier_keys()

            target_x = x + random.randint(-1, 1)
            target_y = y + random.randint(-1, 1)

            pyautogui.moveTo(target_x, target_y, duration=0.03)

            if self.is_interrupted():
                return False

            if modifier:
                win32_key_down(modifier)

            if self.is_interrupted():
                self.sanitize_modifier_keys()
                return False

            pyautogui.click(button=button, duration=click_duration)

            if modifier:
                win32_key_up(modifier)

            self.sanitize_modifier_keys()

        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI Emergency FAILSAFE triggered! Aborting automation.")
            raise
        except Exception as e:
            logger.exception(f"Error during mouse action at ({x}, {y}): {e}")
            self.sanitize_modifier_keys()
            return False
        return True

    def execute_stash_item(self, match: MatchResult) -> bool:
        """Executes Ctrl + Right-Click to store item in the chest."""
        action_key = f"stash_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key):
            return False

        logger.info("Storing matched item...")

        success = self._move_and_click(
            match.center_x,
            match.center_y,
            button=config.ITEM_MOUSE_BUTTON,
            modifier=config.STASH_MODIFIER,
        )

        if success:
            self.last_action_time[action_key] = time.time()

        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_sell_item(self, match: MatchResult) -> bool:
        """Executes Alt + Right-Click to place item into the sales section."""
        action_key = f"sell_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key):
            return False

        logger.info("Placing matched item for sale...")

        success = self._move_and_click(
            match.center_x,
            match.center_y,
            button=config.ITEM_MOUSE_BUTTON,
            modifier=config.SELL_MODIFIER,
        )

        if success:
            self.last_action_time[action_key] = time.time()
            if self.current_sales_slots < config.SALES_SLOTS_CAPACITY:
                self.current_sales_slots += 1
            logger.info(f"Sales Section Capacity: {self.current_sales_slots}/{config.SALES_SLOTS_CAPACITY} slots filled.")

        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_confirm_sell(self, match: MatchResult) -> bool:
        """Clicks the 'Sell' button ONLY if all sales slots are full (current_sales_slots >= CAPACITY)."""
        if self.is_interrupted() or self.current_sales_slots < config.SALES_SLOTS_CAPACITY:
            logger.info(
                f"Sell button detected at ({match.center_x}, {match.center_y}), but sales section is NOT full yet "
                f"({self.current_sales_slots}/{config.SALES_SLOTS_CAPACITY} slots). Skipping click."
            )
            return False

        action_key = f"sell_button_{match.center_x}_{match.center_y}"
        if self.is_in_cooldown(action_key):
            return False

        logger.info("Confirming batch sale...")

        success = self._move_and_click(
            match.center_x,
            match.center_y,
            button="left",
            modifier=None,
        )

        if success:
            self.last_action_time[action_key] = time.time()
            self.current_sales_slots = 0  # Reset sales slot counter after selling batch
            logger.info("Batch sale completed! Reset sales slots to 0.")

        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_open_standard_chest(self, match: MatchResult) -> bool:
        """Clicks Standard Reward Chest to claim rewards."""
        action_key = f"standard_chest_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key, cooldown_seconds=2.0):
            return False

        logger.info("Opening standard reward chest...")

        success = self._move_and_click(match.center_x, match.center_y, button="left")
        if success:
            self.last_action_time[action_key] = time.time()
        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_open_boss_chest(self, match: MatchResult) -> bool:
        """Clicks Boss Reward Chest to claim boss rewards."""
        action_key = f"boss_chest_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key, cooldown_seconds=2.0):
            return False

        logger.info("Opening boss reward chest...")

        success = self._move_and_click(match.center_x, match.center_y, button="left")
        if success:
            self.last_action_time[action_key] = time.time()
        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_open_treasure_chest(self, match: MatchResult) -> bool:
        """Clicks Treasure Reward Chest to claim treasure rewards."""
        action_key = f"treasure_chest_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key, cooldown_seconds=2.0):
            return False

        logger.info("Opening treasure chest...")

        success = self._move_and_click(match.center_x, match.center_y, button="left")
        if success:
            self.last_action_time[action_key] = time.time()
        self.wait(random.uniform(*config.RANDOM_DELAY))
        return success

    def execute_select_cube_mode(self, match: MatchResult) -> bool:
        """Clicks Cube mode header / dropdown option (used to select Alchemy)."""
        action_key = f"cube_mode_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key, cooldown_seconds=1.5):
            return False

        logger.info("Selecting Alchemy mode...")

        success = self._move_and_click(match.center_x, match.center_y, button="left")
        if success:
            self.last_action_time[action_key] = time.time()
        self.wait(random.uniform(0.4, 0.7))
        return success

    def focus_inventory_region(self, region: Dict[str, int]) -> bool:
        """Left-click inventory center so mouse-wheel scroll targets the bag after other UI clicks."""
        if self.is_interrupted() or region is None:
            return False
        cx = int(region["left"] + region["width"] / 2)
        cy = int(region["top"] + region["height"] / 2)
        if not self.validate_coordinates(cx, cy):
            return False
        try:
            self.sanitize_modifier_keys()
            pyautogui.moveTo(cx, cy, duration=0.08)
            if not self.wait(0.03):
                return False
            if self.is_interrupted():
                return False
            pyautogui.click(button="left", duration=0.05)
            self.wait(0.08)
            return True
        except Exception as e:
            logger.debug(f"focus_inventory_region failed: {e}")
            return False

    def scroll_inventory_region(
        self,
        region: Dict[str, int],
        direction: str = "down",
        ticks: int = 4,
        quiet: bool = True,
        ensure_focus: bool = False,
    ) -> bool:
        """
        Moves the cursor to the inventory region center, scrolls the mouse wheel, and instantly restores user cursor position.
        """
        if self.is_interrupted() or region is None:
            return False

        cx = int(region["left"] + region["width"] / 2)
        cy = int(region["top"] + region["height"] / 2)
        if not self.validate_coordinates(cx, cy):
            return False

        delta = abs(int(ticks))
        scroll_amount = delta if direction == "up" else -delta

        try:
            self.sanitize_modifier_keys()
            pyautogui.moveTo(cx, cy, duration=0.04)

            if ensure_focus:
                if self.is_interrupted():
                    return False
                pyautogui.click(button="left", duration=0.03)

            if self.is_interrupted():
                return False
            pyautogui.scroll(scroll_amount)
            self.wait(0.04)
            return True
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI Emergency FAILSAFE triggered during inventory scroll!")
            raise
        except Exception as e:
            logger.exception(f"Inventory scroll failed: {e}")
            return False

    def execute_ui_click(self, match: MatchResult, label: str) -> bool:
        """Generic left-click for UI tab / panel restore actions."""
        action_key = f"ui_{label}_{match.center_x}_{match.center_y}"
        if self.is_interrupted() or self.is_in_cooldown(action_key, cooldown_seconds=1.2):
            return False

        logger.info(f"Restoring UI: {label}...")

        success = self._move_and_click(match.center_x, match.center_y, button="left")
        if success:
            self.last_action_time[action_key] = time.time()
        self.wait(random.uniform(0.35, 0.55))
        return success
