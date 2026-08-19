"""
System-wide hotkeys that keep working when the desktop or a game has focus.

Primary path: WH_KEYBOARD_LL (sees keys before most games consume them).
Fallback: RegisterHotKey on the tool window if the low-level hook cannot be installed.
"""

from __future__ import annotations

import os
import time
import ctypes
from ctypes import wintypes
from typing import Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit

import config
from utils import logger

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105
WM_HOTKEY = 0x0312
LLKHF_INJECTED = 0x10
MOD_NOREPEAT = 0x4000
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200

VK_MAP: Dict[str, int] = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "Esc": 0x1B, "ESC": 0x1B,
    "Space": 0x20, "Enter": 0x0D, "Return": 0x0D, "Tab": 0x09,
}

TYPING_VKS = {0x20, 0x0D, 0x09}  # Space, Enter, Tab — never steal these from text fields

LRESULT = ctypes.c_ssize_t
HHOOK = wintypes.HANDLE
# restype is LRESULT, but the Python callback MUST return a plain int.
# Returning a ctypes instance (c_longlong / LRESULT) makes ctypes raise:
# TypeError: 'c_longlong' object cannot be interpreted as an integer
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def _as_int(value, default: int = 0) -> int:
    """Coerce ctypes integers / None to a Python int for WINFUNCTYPE return values."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        inner = getattr(value, "value", None)
        if inner is None:
            return default
        try:
            return int(inner)
        except (TypeError, ValueError):
            return default


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetShellWindow.restype = wintypes.HWND
user32.GetDesktopWindow.restype = wintypes.HWND
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2
DESKTOP_CLASSES = {"progman", "workerw"}
EXPLORER_FILE_MANAGER_CLASSES = {"cabinetwclass", "explorewclass"}
_OUR_PID = os.getpid()
_FOCUS_CACHE: Tuple[int, bool, float] = (0, False, 0.0)
_FOCUS_CACHE_TTL = 0.12


def vk_from_name(key_name: str) -> Optional[int]:
    if not key_name:
        return None
    return VK_MAP.get(str(key_name).strip())


def is_process_elevated() -> bool:
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def _hwnd_text(hwnd: int, fn, size: int = 512) -> str:
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value or ""


def _process_stem(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            name = buf.value.replace("/", "\\").rsplit("\\", 1)[-1]
            if name.lower().endswith(".exe"):
                name = name[:-4]
            return name.lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _normalized_allow_stems() -> set[str]:
    stems = {"taskbarhero"}
    for raw in getattr(config, "HOTKEY_FOCUS_PROCESSES", []) or []:
        stem = str(raw).strip().lower()
        if stem.endswith(".exe"):
            stem = stem[:-4]
        if stem:
            stems.add(stem)
    return stems


def _title_looks_like_game(title: str) -> bool:
    lowered = (title or "").lower()
    if not lowered:
        return False
    hints = getattr(config, "HOTKEY_FOCUS_TITLE_HINTS", None) or [
        "task bar hero", "taskbarhero", "tbh:"
    ]
    return any(str(hint).lower() in lowered for hint in hints if str(hint).strip())


def foreground_allows_hotkeys() -> bool:
    """True when focus is this tool, the Windows desktop, or TaskBarHero — not Chrome/Explorer/Settings."""
    global _FOCUS_CACHE
    now = time.monotonic()
    hwnd = int(user32.GetForegroundWindow() or 0)
    cached_hwnd, cached_ok, cached_at = _FOCUS_CACHE
    if hwnd == cached_hwnd and (now - cached_at) < _FOCUS_CACHE_TTL:
        return cached_ok

    allowed = False
    try:
        if not hwnd:
            allowed = True  # empty foreground is typically the desktop
        else:
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if int(pid.value) == _OUR_PID:
                allowed = True
            else:
                root = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
                class_name = _hwnd_text(root, user32.GetClassNameW, 256).lower()
                if class_name in EXPLORER_FILE_MANAGER_CLASSES:
                    allowed = False
                elif class_name in DESKTOP_CLASSES:
                    allowed = True
                else:
                    shell = int(user32.GetShellWindow() or 0)
                    desktop = int(user32.GetDesktopWindow() or 0)
                    if hwnd in (shell, desktop) or root in (shell, desktop):
                        allowed = True
                    else:
                        stem = _process_stem(int(pid.value))
                        title = _hwnd_text(root, user32.GetWindowTextW)
                        if not title:
                            title = _hwnd_text(hwnd, user32.GetWindowTextW)
                        allowed = stem in _normalized_allow_stems() or _title_looks_like_game(title)
    except Exception:
        allowed = False

    _FOCUS_CACHE = (hwnd, allowed, now)
    return allowed


def force_window_foreground(hwnd: int, stay_topmost: bool = False) -> None:
    """Raise a window above a focused game/desktop using AttachThreadInput."""
    if not hwnd:
        return
    try:
        hwnd = int(hwnd)
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        fg = user32.GetForegroundWindow()
        pid = wintypes.DWORD(0)
        fg_tid = user32.GetWindowThreadProcessId(fg, ctypes.byref(pid)) if fg else 0
        our_tid = kernel32.GetCurrentThreadId()
        attached = False
        if fg_tid and fg_tid != our_tid:
            attached = bool(user32.AttachThreadInput(fg_tid, our_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(fg_tid, our_tid, False)
        if not stay_topmost:
            user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
    except Exception as exc:
        logger.debug(f"force_window_foreground failed: {exc}")


def _focus_is_text_input() -> bool:
    widget = QApplication.focusWidget()
    return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox))


class _HotkeyNativeFilter(QAbstractNativeEventFilter):
    def __init__(self, on_id: Callable[[int], None]):
        super().__init__()
        self._on_id = on_id

    def nativeEventFilter(self, eventType, message):
        try:
            et = bytes(eventType) if not isinstance(eventType, (bytes, bytearray)) else eventType
            if et in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    self._on_id(int(msg.wParam))
                    return True, 0
        except Exception:
            pass
        return False, 0


class GlobalHotkeyManager(QObject):
    """Dispatches named actions (START_PAUSE, QUICK_CAPTURE, ...) from OS-level keys."""

    activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hwnd = 0
        self._mode = "none"
        self._vk_to_action: Dict[int, str] = {}
        self._held: set[int] = set()
        self._hook = None
        self._proc = None
        self._reg_ids: Dict[int, str] = {}
        self._next_id = 1
        self._filter: Optional[_HotkeyNativeFilter] = None

    @property
    def mode(self) -> str:
        return self._mode

    def start(self, hwnd: int) -> None:
        self._hwnd = int(hwnd) if hwnd else 0
        if self._install_hook():
            self._mode = "hook"
            extra = ""
            if not is_process_elevated():
                extra = " Run as Administrator if TaskBarHero still swallows shortcuts."
            logger.info("They work only while this tool, the desktop, or TaskBarHero is focused." + extra)
            return

        err = kernel32.GetLastError()
        # RegisterHotKey always steals keys from every app, so it is not used for scoped hotkeys.
        logger.warning(
            f"Low-level keyboard hook failed (GetLastError={err}). "
            "Scoped hotkeys require the hook; shortcuts will work only while TBH-Tool itself is focused."
        )
        self._mode = "local"

    def set_bindings(self, hotkeys: Dict[str, str]) -> None:
        mapping: Dict[int, str] = {}
        for action, key_name in (hotkeys or {}).items():
            vk = vk_from_name(key_name)
            if vk is None:
                logger.warning(f"Unknown hotkey name '{key_name}' for {action}")
                continue
            if vk in mapping and mapping[vk] != action:
                logger.warning(f"Hotkey {key_name} assigned to both {mapping[vk]} and {action}; using {action}")
            mapping[vk] = action
        self._vk_to_action = mapping
        if self._mode == "register":
            self._register_win_hotkeys()

    def stop(self) -> None:
        self._unregister_win_hotkeys()
        if self._filter:
            app = QApplication.instance()
            if app:
                app.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
        self._proc = None
        self._mode = "none"
        self._held.clear()

    def _install_hook(self) -> bool:
        # Keep a bound reference so ctypes does not garbage-collect the callback.
        self._proc = HOOKPROC(self._low_level_proc)
        hmod = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, hmod, 0)
        if not self._hook:
            self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        return bool(self._hook)

    def _call_next_hook(self, nCode, wParam, lParam) -> int:
        try:
            result = user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
        except Exception:
            logger.exception("CallNextHookEx failed")
            return 0
        return _as_int(result)

    def _low_level_proc(self, nCode, wParam, lParam):
        try:
            nCode = _as_int(nCode)
            wParam = _as_int(wParam)
            if nCode >= 0:
                info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(info.vkCode)
                if wParam in (WM_KEYUP, WM_SYSKEYUP):
                    self._held.discard(vk)
                elif wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if not (info.flags & LLKHF_INJECTED) and vk in self._vk_to_action:
                        if vk not in self._held:
                            if not foreground_allows_hotkeys():
                                return self._call_next_hook(nCode, wParam, lParam)
                            if vk in TYPING_VKS and _focus_is_text_input():
                                return self._call_next_hook(nCode, wParam, lParam)
                            self._held.add(vk)
                            action = self._vk_to_action[vk]
                            QTimer.singleShot(0, lambda a=action: self.activated.emit(a))
                            return 1
        except Exception:
            logger.exception("Low-level keyboard hook callback failed")
        return self._call_next_hook(nCode, wParam, lParam)

    def _register_win_hotkeys(self) -> None:
        self._unregister_win_hotkeys()
        if not self._hwnd:
            return
        for vk, action in self._vk_to_action.items():
            hid = self._next_id
            self._next_id += 1
            if user32.RegisterHotKey(self._hwnd, hid, MOD_NOREPEAT, vk):
                self._reg_ids[hid] = action
            else:
                logger.warning(f"RegisterHotKey failed for {action} (VK=0x{vk:02X}). Key may already be in use.")

    def _unregister_win_hotkeys(self) -> None:
        if not self._hwnd:
            self._reg_ids.clear()
            return
        for hid in list(self._reg_ids):
            user32.UnregisterHotKey(self._hwnd, hid)
        self._reg_ids.clear()

    def _on_register_id(self, hotkey_id: int) -> None:
        action = self._reg_ids.get(hotkey_id)
        if action:
            self.activated.emit(action)
