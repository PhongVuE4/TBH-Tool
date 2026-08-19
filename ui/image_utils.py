"""Qt image and screen-coordinate helpers."""
from typing import Optional, Tuple
import cv2
import mss
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget
from utils import logger

def bgr_to_qpixmap(img_bgr: np.ndarray) -> Optional["QPixmap"]:
    """Convert a BGR numpy image to a QPixmap with an owned pixel buffer."""
    if img_bgr is None or getattr(img_bgr, "size", 0) == 0:
        return None
    rgb = np.ascontiguousarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def grab_primary_monitor_bgr() -> Optional[np.ndarray]:
    try:
        with mss.MSS() as sct:
            primary_mon = sct.monitors[1]
            sct_img = sct.grab(primary_mon)
            return np.ascontiguousarray(np.array(sct_img, dtype=np.uint8)[:, :, :3])
    except Exception as e:
        logger.error(f"Error capturing overlay background screenshot: {e}")
        return None


def apply_overlay_window_chrome(widget: QWidget) -> None:
    """Top-level fullscreen overlay that can take keyboard focus (not Qt.Tool)."""
    widget.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.Window
    )
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
    widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
    screen = QApplication.primaryScreen()
    if screen:
        widget.setGeometry(screen.geometry())


def logical_to_physical_xy(x: int, y: int) -> Tuple[int, int]:
    """Map Qt/pyautogui logical pixels to mss physical pixels."""
    screen = QApplication.primaryScreen()
    dpr = float(screen.devicePixelRatio()) if screen else 1.0
    return int(round(x * dpr)), int(round(y * dpr))


