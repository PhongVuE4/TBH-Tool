"""Fullscreen selection overlays for region measurement and template capture."""
from typing import Optional
import numpy as np
from PyQt6.QtCore import QEvent, QObject, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget
from hotkeys import force_window_foreground
from utils import logger
from ui.image_utils import apply_overlay_window_chrome, bgr_to_qpixmap, grab_primary_monitor_bgr, logical_to_physical_xy

class OverlayEscFilter(QObject):
    """Qt-side ESC interceptor while an overlay is visible (backup for the OS-level hook)."""
    def __init__(self, overlay_widget, main_win):
        super().__init__(overlay_widget)
        self.overlay_widget = overlay_widget
        self.main_win = main_win

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Cancel):
                logger.warning("[STOPPED] Emergency Stop triggered via ESC key during screen overlay!")
                if self.main_win and hasattr(self.main_win, "cancel_active_overlay"):
                    self.main_win.cancel_active_overlay(emergency_stop=True)
                else:
                    if self.main_win and hasattr(self.main_win, "trigger_emergency_stop"):
                        self.main_win.trigger_emergency_stop()
                    self.overlay_widget.close()
                return True
        return super().eventFilter(obj, event)


class FrozenScreenOverlay(QWidget):
    """Fullscreen frozen screenshot overlay that can take focus above a game window."""

    def __init__(self, main_win=None):
        super().__init__(None)
        self.main_win = main_win
        apply_overlay_window_chrome(self)
        self.esc_filter = OverlayEscFilter(self, self.main_win)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self.esc_filter)

        img_bgr = grab_primary_monitor_bgr()
        self.img_bgr = img_bgr
        self.bg_pixmap = bgr_to_qpixmap(img_bgr) if img_bgr is not None else None

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start_pos = None
        self.end_pos = None
        self.is_drawing = False

    def showEvent(self, event):
        super().showEvent(event)
        self._claim_input()
        QTimer.singleShot(0, self._claim_input)
        QTimer.singleShot(80, self._claim_input)

    def _claim_input(self):
        try:
            if not self.isVisible():
                return
            self.raise_()
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.grabKeyboard()
            force_window_foreground(int(self.winId()), stay_topmost=True)
        except RuntimeError:
            pass

    def closeEvent(self, event):
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self.esc_filter)
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Cancel):
            if self.main_win and hasattr(self.main_win, "cancel_active_overlay"):
                self.main_win.cancel_active_overlay(emergency_stop=True)
            else:
                self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def _selection_rect(self) -> Optional[QRect]:
        if not self.start_pos or not self.end_pos:
            return None
        rect = QRect(self.start_pos, self.end_pos).normalized()
        if rect.width() <= 5 or rect.height() <= 5:
            return None
        return rect

    def _physical_crop_rect(self) -> Optional[tuple]:
        rect = self._selection_rect()
        if rect is None:
            return None
        x, y = logical_to_physical_xy(rect.x(), rect.y())
        x2, y2 = logical_to_physical_xy(rect.x() + rect.width(), rect.y() + rect.height())
        w, h = max(1, x2 - x), max(1, y2 - y)
        return x, y, w, h


# --- NATIVE GUI REGION MEASURING OVERLAY ---
class GuiRegionOverlay(FrozenScreenOverlay):
    region_selected_signal = pyqtSignal(str, int, int, int, int)

    def __init__(self, region_name: str, main_win=None):
        super().__init__(main_win=main_win)
        self.region_name = region_name

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.bg_pixmap:
            painter.drawPixmap(self.rect(), self.bg_pixmap)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        is_vietnamese = getattr(self.main_win, "language", "vi") == "vi"
        title = (
            "VÙNG TÚI ĐỒ" if self.region_name == "INVENTORY_REGION" else "VÙNG CỬA SỔ GAME"
        ) if is_vietnamese else (
            "INVENTORY REGION" if self.region_name == "INVENTORY_REGION" else "GAME WINDOW REGION"
        )
        banner_text = (
            f"ĐO {title}: Nhấn giữ và kéo chuột qua vùng cần đo (ESC để dừng khẩn cấp)"
            if is_vietnamese else
            f"MEASURE {title}: Click & Drag mouse over region area (ESC for Emergency Stop)"
        )

        font = QFont("Inter", 11, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(banner_text) + 40
        banner_rect = QRect(self.width() // 2 - text_width // 2, 16, text_width, 40)

        painter.setPen(QPen(QColor("#27a644"), 1))
        painter.setBrush(QColor("#1b1b1c"))
        painter.drawRoundedRect(banner_rect, 6, 6)

        painter.setPen(QColor("#66df75"))
        painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, banner_text)

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            
            if self.bg_pixmap:
                painter.drawPixmap(rect, self.bg_pixmap, rect)

            painter.setPen(QPen(QColor("#27a644"), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            info_str = f"{rect.width()} x {rect.height()} px"
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("JetBrains Mono", 10, QFont.Weight.Bold))
            painter.drawText(rect.x() + 6, rect.y() + 20, info_str)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.end_pos = event.pos()
            rect = self._selection_rect()
            if rect is not None:
                self.region_selected_signal.emit(
                    self.region_name, rect.x(), rect.y(), rect.width(), rect.height()
                )
            self.close()


# --- NATIVE GUI ITEM CAPTURE OVERLAY ---
class GuiItemCaptureOverlay(FrozenScreenOverlay):
    capture_completed_signal = pyqtSignal(object)

    def __init__(self, main_win=None):
        super().__init__(main_win=main_win)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.bg_pixmap:
            painter.drawPixmap(self.rect(), self.bg_pixmap)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))

        is_vietnamese = getattr(self.main_win, "language", "vi") == "vi"
        banner_text = (
            "CHỤP MẪU VẬT PHẨM: Nhấn giữ và kéo chuột qua hình vật phẩm (ESC để dừng khẩn cấp)"
            if is_vietnamese else
            "ITEM CAPTURE TOOL: Click & Drag mouse over item graphic (ESC for Emergency Stop)"
        )
        
        font = QFont("Inter", 11, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(banner_text) + 40
        banner_rect = QRect(self.width() // 2 - text_width // 2, 16, text_width, 40)

        painter.setPen(QPen(QColor("#a3c9ff"), 1))
        painter.setBrush(QColor("#1b1b1c"))
        painter.drawRoundedRect(banner_rect, 6, 6)

        painter.setPen(QColor("#a3c9ff"))
        painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, banner_text)

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()

            if self.bg_pixmap:
                painter.drawPixmap(rect, self.bg_pixmap, rect)

            painter.setPen(QPen(QColor("#0078d4"), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            info_str = f"{rect.width()} x {rect.height()} px"
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("JetBrains Mono", 10, QFont.Weight.Bold))
            painter.drawText(rect.x() + 6, rect.y() + 20, info_str)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            self.end_pos = event.pos()
            crop_rect = self._physical_crop_rect()
            if crop_rect is not None and self.img_bgr is not None:
                x, y, w, h = crop_rect
                sh, sw = self.img_bgr.shape[:2]
                x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(sw, x + w), min(sh, y + h)
                crop = self.img_bgr[y1:y2, x1:x2].copy()
                if crop.size > 0:
                    self.capture_completed_signal.emit(crop)
            self.close()


