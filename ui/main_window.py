"""TBH-Tool's main PyQt window and its presentation-level event wiring."""
from pathlib import Path
import datetime
import html
import re
import sys
from typing import Optional
import cv2
import mss
import numpy as np
import pyautogui
from PyQt6.QtCore import QDir, QEvent, QLockFile, QPoint, QRect, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QIcon
from PyQt6.QtWidgets import QAbstractButton, QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PyQt6.QtSvgWidgets import QSvgWidget
import config
from app.automation_worker import AutomationWorker
from capture import trim_yellow_border_if_present
from get_region import save_region_to_config
from hotkeys import GlobalHotkeyManager, force_window_foreground
from utils import attach_gui_log_callback, install_error_logging_hooks, log_event, logger
from ui.dialogs import CaptureSaveDialog, MeasureChoiceDialog, SettingsDialog
from ui.image_utils import grab_primary_monitor_bgr, logical_to_physical_xy
from ui.overlays import GuiItemCaptureOverlay, GuiRegionOverlay
from ui.styles import STITCH_DARK_STYLE

KEY_NAME_TO_QT = {
    "F1": Qt.Key.Key_F1, "F2": Qt.Key.Key_F2, "F3": Qt.Key.Key_F3, "F4": Qt.Key.Key_F4,
    "F5": Qt.Key.Key_F5, "F6": Qt.Key.Key_F6, "F7": Qt.Key.Key_F7, "F8": Qt.Key.Key_F8,
    "F9": Qt.Key.Key_F9, "F10": Qt.Key.Key_F10, "F11": Qt.Key.Key_F11, "F12": Qt.Key.Key_F12,
    "Esc": Qt.Key.Key_Escape, "ESC": Qt.Key.Key_Escape,
    "Space": Qt.Key.Key_Space, "Enter": Qt.Key.Key_Return, "Return": Qt.Key.Key_Return, "Tab": Qt.Key.Key_Tab,
}

class TBHToolMainWindow(QMainWindow):
    gui_log_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        base_dir = Path(__file__).resolve().parent
        self.assets_dir = base_dir / "assets"

        self.setWindowIcon(QIcon(str(self.assets_dir / "TBH-Tool.ico")))
        self.setWindowTitle("TBH-Tool v2.0")
        
        # Let Windows own the caption, resize border, and window-state
        # transitions.  The application header below remains custom-styled.
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(900, 500)
        self.resize(980, 590)
        self.worker = AutomationWorker()
        self.gui_log_signal.connect(self.append_log)
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.update_status_display)
        self.worker.templates_count_signal.connect(self.update_templates_count)
        attach_gui_log_callback(lambda level, msg: self.gui_log_signal.emit(level, msg))

        self.active_overlay = None
        self._drag_pos = None
        self._hotkeys_started = False
        self._pending_tool_timer: Optional[QTimer] = None
        self.language = config.load_config_json().get("LANGUAGE", "vi")
        self.hotkeys = GlobalHotkeyManager(self)
        self.hotkeys.activated.connect(self.on_global_hotkey)

        self.init_ui()
        self.retranslate_ui()
        self.load_window_state()

        QTimer.singleShot(100, self.async_startup_init)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._hotkeys_started:
            hwnd = int(self.winId())
            if hwnd:
                self.hotkeys.set_bindings(config.HOTKEYS)
                self.hotkeys.start(hwnd)
                self._hotkeys_started = True

    def reload_global_hotkeys(self):
        self.hotkeys.set_bindings(config.HOTKEYS)
        self.update_hotkey_badges()

    def _cancel_pending_tool(self):
        timer = self._pending_tool_timer
        self._pending_tool_timer = None
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def _schedule_after_hide(self, msec: int, callback) -> None:
        self._cancel_pending_tool()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        self._pending_tool_timer = timer
        timer.start(msec)

    def _overlay_is_up(self) -> bool:
        if self.active_overlay is None:
            return False
        try:
            return self.active_overlay.isVisible()
        except RuntimeError:
            self.active_overlay = None
            return False

    def cancel_active_overlay(self, emergency_stop: bool = False):
        self._cancel_pending_tool()
        if emergency_stop:
            self.trigger_emergency_stop()
        overlay = self.active_overlay
        self.active_overlay = None
        if overlay is not None:
            try:
                overlay.close()
            except RuntimeError:
                pass
        if not self.isVisible():
            self.show()

    def _restore_for_dialog(self):
        self.show()
        self.raise_()
        self.activateWindow()
        force_window_foreground(int(self.winId()), stay_topmost=False)

    def on_global_hotkey(self, action: str):
        overlay_up = self._overlay_is_up()
        modal = QApplication.activeModalWidget()

        if action == "EMERGENCY_STOP":
            if overlay_up:
                self.cancel_active_overlay(emergency_stop=True)
                return
            if modal is not None:
                modal.reject()
                return
            self.trigger_emergency_stop()
            return

        if overlay_up or modal is not None or self._pending_tool_timer is not None:
            return

        if action == "START_PAUSE":
            self.toggle_start_pause()
        elif action == "MEASURE_REGION":
            self.tool_measure_region()
        elif action == "QUICK_CAPTURE":
            self.start_quick_hover_capture(immediate=True)
        elif action == "FREEZE_CAPTURE":
            self.start_freeze_capture()
        elif action == "RELOAD_TEMPLATES":
            self.tool_reload_templates()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setStyleSheet(STITCH_DARK_STYLE)

        # --- 1. Compact Windows Header Bar ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("HeaderFrame")
        self.header_frame.setFixedHeight(36)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 0, 0, 0)
        header_layout.setSpacing(12)

        logo = QSvgWidget(str(self.assets_dir / "PV-logo.svg"))
        logo.setFixedSize(28, 28)
        header_layout.addWidget(logo)

        self.lbl_st_tag = QLabel("ENGINE STATUS:")
        self.lbl_st_tag.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 10px; color: #8a919e; font-weight: bold;")
        header_layout.addWidget(self.lbl_st_tag)

        self.lbl_status_val = QLabel("● STOPPED")
        self.lbl_status_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #8a919e;")
        header_layout.addWidget(self.lbl_status_val)

        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.VLine)
        div2.setStyleSheet("color: #404752;")
        header_layout.addWidget(div2)

        self.lbl_tmpl_tag = QLabel("TEMPLATES:")
        self.lbl_tmpl_tag.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 10px; color: #8a919e; font-weight: bold;")
        header_layout.addWidget(self.lbl_tmpl_tag)

        self.lbl_templates_count = QLabel("0")
        self.lbl_templates_count.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #fabd00;")
        header_layout.addWidget(self.lbl_templates_count)

        header_layout.addStretch()

        self.btn_language = QPushButton("VI")
        self.btn_language.setObjectName("SettingsBtn")
        self.btn_language.setFixedHeight(36)
        self.btn_language.clicked.connect(self.toggle_language)
        header_layout.addWidget(self.btn_language)

        self.btn_settings = QPushButton("[ ⚙ Settings ]")
        self.btn_settings.setObjectName("SettingsBtn")
        self.btn_settings.setFixedHeight(36)
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.btn_settings)

        main_layout.addWidget(self.header_frame)

        # --- Content Body Area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # --- 2. Primary Controls Row ---
        primary_layout = QHBoxLayout()
        primary_layout.setSpacing(10)

        self.btn_start = QPushButton()
        self.btn_start.setObjectName("StartBtn")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_start_content = QHBoxLayout(self.btn_start)
        btn_start_content.setContentsMargins(16, 0, 16, 0)
        self.lbl_start_txt = QLabel("[ ▶ START AUTOMATION ]")
        self.lbl_start_txt.setStyleSheet("font-size: 15px; font-weight: bold; color: #66df75;")
        self.kbd_start = QLabel(config.HOTKEYS.get("START_PAUSE", "F1"))
        self.kbd_start.setObjectName("KbdBadge")
        btn_start_content.addWidget(self.lbl_start_txt)
        btn_start_content.addStretch()
        btn_start_content.addWidget(self.kbd_start)
        self.btn_start.clicked.connect(self.toggle_start_pause)

        self.btn_stop = QPushButton()
        self.btn_stop.setObjectName("StopBtn")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_stop_content = QHBoxLayout(self.btn_stop)
        btn_stop_content.setContentsMargins(16, 0, 16, 0)
        self.lbl_stop_txt = QLabel("[ ⛔ EMERGENCY STOP ]")
        self.lbl_stop_txt.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffb4ab;")
        self.kbd_stop = QLabel(config.HOTKEYS.get("EMERGENCY_STOP", "Esc"))
        self.kbd_stop.setObjectName("KbdBadgeEsc")
        btn_stop_content.addWidget(self.lbl_stop_txt)
        btn_stop_content.addStretch()
        btn_stop_content.addWidget(self.kbd_stop)
        self.btn_stop.clicked.connect(self.trigger_emergency_stop)

        primary_layout.addWidget(self.btn_start, 1)
        primary_layout.addWidget(self.btn_stop, 1)
        content_layout.addLayout(primary_layout)

        # --- 3. Secondary Tools Grid Row (4 Dedicated Tool Buttons) ---
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)

        # Measure Region Button
        btn_measure = QPushButton()
        btn_measure.setObjectName("ToolBtn")
        btn_measure_lay = QHBoxLayout(btn_measure)
        btn_measure_lay.setContentsMargins(8, 0, 8, 0)
        self.lbl_measure = QLabel("[ Measure Region ]")
        self.lbl_measure.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.kbd_m = QLabel(config.HOTKEYS.get("MEASURE_REGION", "F2"))
        self.kbd_m.setObjectName("KbdBadgeTool")
        btn_measure_lay.addWidget(self.lbl_measure)
        btn_measure_lay.addStretch()
        btn_measure_lay.addWidget(self.kbd_m)
        btn_measure.clicked.connect(self.tool_measure_region)

        # Quick Hover Capture Button
        btn_quick = QPushButton()
        btn_quick.setObjectName("ToolBtn")
        btn_quick_lay = QHBoxLayout(btn_quick)
        btn_quick_lay.setContentsMargins(8, 0, 8, 0)
        self.lbl_quick = QLabel("[ ⚡ Quick Capture ]")
        self.lbl_quick.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.kbd_q = QLabel(config.HOTKEYS.get("QUICK_CAPTURE", "F3"))
        self.kbd_q.setObjectName("KbdBadgeTool")
        btn_quick_lay.addWidget(self.lbl_quick)
        btn_quick_lay.addStretch()
        btn_quick_lay.addWidget(self.kbd_q)
        btn_quick.clicked.connect(self.start_quick_hover_capture)

        # Freeze Snipper Button
        btn_freeze = QPushButton()
        btn_freeze.setObjectName("ToolBtn")
        btn_freeze_lay = QHBoxLayout(btn_freeze)
        btn_freeze_lay.setContentsMargins(8, 0, 8, 0)
        self.lbl_freeze = QLabel("[ ✂ Freeze Snipper ]")
        self.lbl_freeze.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.kbd_f = QLabel(config.HOTKEYS.get("FREEZE_CAPTURE", "F4"))
        self.kbd_f.setObjectName("KbdBadgeTool")
        btn_freeze_lay.addWidget(self.lbl_freeze)
        btn_freeze_lay.addStretch()
        btn_freeze_lay.addWidget(self.kbd_f)
        btn_freeze.clicked.connect(self.start_freeze_capture)

        # Reload Templates Button
        btn_reload = QPushButton()
        btn_reload.setObjectName("ToolBtn")
        btn_reload_lay = QHBoxLayout(btn_reload)
        btn_reload_lay.setContentsMargins(8, 0, 8, 0)
        self.lbl_reload = QLabel("[ Reload Templates ]")
        self.lbl_reload.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.kbd_r = QLabel(config.HOTKEYS.get("RELOAD_TEMPLATES", "F5"))
        self.kbd_r.setObjectName("KbdBadgeTool")
        btn_reload_lay.addWidget(self.lbl_reload)
        btn_reload_lay.addStretch()
        btn_reload_lay.addWidget(self.kbd_r)
        btn_reload.clicked.connect(self.tool_reload_templates)

        tools_layout.addWidget(btn_measure, 1)
        tools_layout.addWidget(btn_quick, 1)
        tools_layout.addWidget(btn_freeze, 1)
        tools_layout.addWidget(btn_reload, 1)
        content_layout.addLayout(tools_layout)

        # --- 4. Integrated Console Logs Container ---
        console_frame = QFrame()
        console_frame.setObjectName("ConsoleContainer")
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        log_bar = QFrame()
        log_bar.setStyleSheet("background-color: #1b1b1c; border-bottom: 1px solid #404752;")
        log_bar_lay = QHBoxLayout(log_bar)
        log_bar_lay.setContentsMargins(10, 4, 10, 4)

        self.lbl_log_title = QLabel("SYSTEM LOGS")
        self.lbl_log_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #8a919e; letter-spacing: 0.5px;")

        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)

        btn_clear = QPushButton("🗑 Clear")
        btn_clear.setStyleSheet("background: transparent; border: none; color: #c0c7d4; font-size: 10px;")
        btn_clear.clicked.connect(self.clear_logs)

        log_bar_lay.addWidget(self.lbl_log_title)
        log_bar_lay.addStretch()
        log_bar_lay.addWidget(self.chk_autoscroll)
        log_bar_lay.addWidget(btn_clear)
        console_layout.addWidget(log_bar)

        self.txt_console = QTextEdit()
        self.txt_console.setObjectName("LogConsole")
        self.txt_console.setReadOnly(True)
        console_layout.addWidget(self.txt_console)

        content_layout.addWidget(console_frame, 1)
        main_layout.addWidget(content_widget, 1)

        # --- 5. Bottom Status Bar ---
        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")

        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(0)

        # Left side
        # status_left = QLabel("TBH-Tool v2.0")
        # status_left.setStyleSheet("""
        #     font-family: 'JetBrains Mono';
        #     font-size: 9px;
        #     color: #68717D;
        # """)

        # Right side - Author
        status_author = QLabel("© 2026 Phong Vu • TBH-Tool")
        status_author.setStyleSheet("""
            font-family: 'JetBrains Mono';
            font-size: 13px;
            color: #68717D;
        """)

        # status_layout.addWidget(status_left)
        status_layout.addStretch()
        status_layout.addWidget(status_author)
        main_layout.addWidget(status_bar)

    def update_hotkey_badges(self):
        """Updates hotkey badge texts on main UI when user changes hotkeys in Settings."""
        self.kbd_start.setText(config.HOTKEYS.get("START_PAUSE", "F1"))
        self.kbd_stop.setText(config.HOTKEYS.get("EMERGENCY_STOP", "Esc"))
        self.kbd_m.setText(config.HOTKEYS.get("MEASURE_REGION", "F2"))
        self.kbd_q.setText(config.HOTKEYS.get("QUICK_CAPTURE", "F3"))
        self.kbd_f.setText(config.HOTKEYS.get("FREEZE_CAPTURE", "F4"))
        self.kbd_r.setText(config.HOTKEYS.get("RELOAD_TEMPLATES", "F5"))

    def toggle_language(self):
        self.language = "vi" if self.language == "en" else "en"
        cfg = config.load_config_json()
        cfg["LANGUAGE"] = self.language
        config.save_config_json(cfg)
        self.retranslate_ui()
        self.append_log(
            "SYSTEM",
            "Đã chuyển sang tiếng Việt." if self.language == "vi" else "Switched to English.",
        )

    def retranslate_ui(self):
        is_vietnamese = self.language == "vi"
        texts = {
            "status": "TRẠNG THÁI MÁY:" if is_vietnamese else "ENGINE STATUS:",
            "templates": "MẪU:" if is_vietnamese else "TEMPLATES:",
            "settings": "[ ⚙ Cài đặt ]" if is_vietnamese else "[ ⚙ Settings ]",
            "start": "[ ▶ BẮT ĐẦU TỰ ĐỘNG ]" if is_vietnamese else "[ ▶ START AUTOMATION ]",
            "pause": "[ ▶ TẠM DỪNG TỰ ĐỘNG ]" if is_vietnamese else "[ ▶ PAUSE AUTOMATION ]",
            "resume": "[ ▶ TIẾP TỤC TỰ ĐỘNG ]" if is_vietnamese else "[ ▶ RESUME AUTOMATION ]",
            "stop": "[ ⛔ DỪNG KHẨN CẤP ]" if is_vietnamese else "[ ⛔ EMERGENCY STOP ]",
            "measure": "[ Đo vùng màn hình ]" if is_vietnamese else "[ Measure Region ]",
            "quick": "[ ⚡ Chụp nhanh ]" if is_vietnamese else "[ ⚡ Quick Capture ]",
            "freeze": "[ ✂ Cắt ảnh đóng băng ]" if is_vietnamese else "[ ✂ Freeze Snipper ]",
            "reload": "[ Tải lại mẫu ]" if is_vietnamese else "[ Reload Templates ]",
            "logs": "NHẬT KÝ HỆ THỐNG" if is_vietnamese else "SYSTEM LOGS",
            "autoscroll": "Tự cuộn" if is_vietnamese else "Auto-scroll",
        }
        self.lbl_st_tag.setText(texts["status"])
        self.lbl_tmpl_tag.setText(texts["templates"])
        self.btn_settings.setText(texts["settings"])
        self.btn_language.setText("EN" if is_vietnamese else "VI")
        if not self.worker._running:
            self.lbl_start_txt.setText(texts["start"])
        elif self.worker._paused:
            self.lbl_start_txt.setText(texts["resume"])
        else:
            self.lbl_start_txt.setText(texts["pause"])
        self.lbl_stop_txt.setText(texts["stop"])
        self.lbl_measure.setText(texts["measure"])
        self.lbl_quick.setText(texts["quick"])
        self.lbl_freeze.setText(texts["freeze"])
        self.lbl_reload.setText(texts["reload"])
        self.lbl_log_title.setText(texts["logs"])
        self.chk_autoscroll.setText(texts["autoscroll"])

    def _get_resize_edges(self, global_pos):
        if self.isMaximized():
            return Qt.Edge(0)

        pos = self.mapFromGlobal(global_pos)
        rect = self.rect()

        margin = 8
        edges = Qt.Edge(0)

        if pos.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= rect.width() - margin:
            edges |= Qt.Edge.RightEdge

        if pos.y() <= margin:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= rect.height() - margin:
            edges |= Qt.Edge.BottomEdge

        return edges


    def _is_header_button(self, global_pos):
        local_pos = self.header_frame.mapFromGlobal(global_pos)

        if not self.header_frame.rect().contains(local_pos):
            return False

        widget = self.header_frame.childAt(local_pos)

        while widget is not None and widget is not self.header_frame:
            if isinstance(widget, QAbstractButton):
                return True

            widget = widget.parentWidget()

        return False

    def _clear_header_drag(self):
        self._header_drag_start = None
        self._header_drag_offset = None
        self._header_drag_was_maximized = False
        self._header_drag_normal_geometry = QRect()

    def eventFilter(self, obj, event):
        if obj is self.header_frame:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                if not self.isMaximized():
                    edges = self._get_resize_edges(global_pos)
                    if edges != Qt.Edge(0):
                        window = self.windowHandle()
                        if window is not None and window.startSystemResize(edges):
                            return True

                self._header_drag_start = global_pos
                self._header_drag_was_maximized = self.isMaximized()
                self._header_drag_normal_geometry = self.normalGeometry()
                if not self._header_drag_was_maximized:
                    self._header_drag_offset = self._header_drag_start - self.frameGeometry().topLeft()
                return True

            if event.type() == QEvent.Type.MouseMove and self._header_drag_start is not None:
                if not (event.buttons() & Qt.MouseButton.LeftButton):
                    self._clear_header_drag()
                    return True

                global_pos = event.globalPosition().toPoint()
                if self._header_drag_was_maximized:
                    if (global_pos - self._header_drag_start).manhattanLength() < QApplication.startDragDistance():
                        return True

                    normal = self._header_drag_normal_geometry
                    if not normal.isValid():
                        normal = self.geometry()
                    maximized = self.frameGeometry()
                    ratio = (self._header_drag_start.x() - maximized.left()) / max(1, maximized.width())
                    offset_x = round(max(0.0, min(1.0, ratio)) * normal.width())
                    offset_y = min(self.header_frame.height() - 1, self._header_drag_start.y() - maximized.top())

                    self.showNormal()
                    self._header_drag_offset = QPoint(offset_x, offset_y)
                    self._header_drag_was_maximized = False

                self.move(global_pos - self._header_drag_offset)
                return True

            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._clear_header_drag()
                return True

            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                self.restore_or_maximize()
                return True

        # Frameless windows have no native resize border.  This runs for mouse
        # events from the window and its child widgets, while buttons retain
        # their normal click behaviour.
        if not self.isMaximized() and not isinstance(obj, QAbstractButton):
            if hasattr(event, "globalPosition"):
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)
                if self.rect().contains(local_pos):
                    edges = self._get_resize_edges(global_pos)

                    if event.type() == QEvent.Type.MouseMove:
                        cursor_by_edges = {
                            Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
                            Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
                            Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeBDiagCursor,
                            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeBDiagCursor,
                            Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
                            Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
                            Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
                            Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
                        }
                        if edges in cursor_by_edges:
                            self.setCursor(cursor_by_edges[edges])
                        else:
                            self.unsetCursor()

                    elif (
                        event.type() == QEvent.Type.MouseButtonPress
                        and event.button() == Qt.MouseButton.LeftButton
                        and edges != Qt.Edge(0)
                    ):
                        window = self.windowHandle()
                        if window is not None and window.startSystemResize(edges):
                            return True

        return super().eventFilter(obj, event)

    def async_startup_init(self):
        count = self.worker.initialize_engines()

    def restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def restore_or_maximize(self):
        if self.windowState() & Qt.WindowState.WindowMaximized:
            self.restore_window()
        else:
            self.showMaximized()

    def toggle_maximize(self):
        self.restore_or_maximize()

    def _localize_log_message(self, message: str) -> str:
        """Translate GUI log text without changing technical identifiers."""
        if self.language != "vi":
            return message

        replacements = (
            ("[PAUSED]", "[TẠM DỪNG]"),
            ("[RESUMED]", "[TIẾP TỤC]"),
            ("[STOPPED]", "[ĐÃ DỪNG]"),
            ("[+] QUICK HOVER CAPTURE:", "[+] CHỤP NHANH:"),
            ("capturing at current cursor position...", "đang chụp tại vị trí con trỏ chuột..."),
            ("Searching for item...", "Đang tìm vật phẩm..."),
            ("Automation Engine Active!", "Tool đã hoạt động!"),
            ("PREPARING AUTOMATION", "Chờ một chút..."),
            ("Please switch to your Game window in 3 seconds...", "Hãy chuyển sang cửa sổ game trong 3 giây..."),
            ("Starting automation in:", "Tool bắt đầu sau:"),
            ("Stashed:", "Đã cất vào kho:"),
            ("Placed for sale:", "Đã đặt bán:"),
            ("Clicked Batch Confirm Sell!", "Đã nhấn xác nhận bán hàng loạt!"),
            ("Batch sale completed! Reset sales slots to 0.", "Đã hoàn tất bán hàng loạt! Đã đặt lại số ô bán về 0."),
            ("Reloaded", "Đã tải lại"),
            ("template assets into memory cache.", "mẫu vào bộ nhớ đệm."),
            ("Emergency Stop triggered!", "Đã kích hoạt dừng khẩn cấp!"),
            ("Automation engine paused.", "Tool đã tạm dừng."),
            ("Automation engine resumed.", "Tool đã tiếp tục."),
            ("Connection Lost detected", "Phát hiện mất kết nối"),
            ("Waiting...", "Đang chờ..."),
            ("Saved item template:", "Đã lưu mẫu vật phẩm:"),
            ("Configuration updated via Settings dialog.", "Đã cập nhật cấu hình từ cửa sổ cài đặt."),
            ("Error during quick hover capture:", "Lỗi khi chụp nhanh tại vị trí chuột:"),
            ("Loading template assets...", "Đang tải mẫu..."),
            ("Successfully cached", "Đã lưu vào bộ nhớ đệm"),
            ("templates in memory.", "mẫu."),
        )
        localized = str(message)
        for source, target in replacements:
            localized = localized.replace(source, target)
        localized = re.sub(
            r"Đã lưu vào bộ nhớ đệm (\d+) mẫu\.",
            r"Đã lưu \1 mẫu vào bộ nhớ đệm.",
            localized,
        )
        return localized
    
    @pyqtSlot(str, str)
    def append_log(self, level: str, msg: str):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        color_map = {
            "DEBUG": "#8a919e",
            "SYSTEM": "#a3c9ff",
            "INFO": "#e5e2e1",
            "ACTION": "#66df75",
            "WARN": "#fabd00",
            "WARNING": "#fabd00",
            "ERROR": "#ffb4ab",
            "CRITICAL": "#ff8a80",
        }
        level_key = (level or "INFO").upper()
        c = color_map.get(level_key, "#e5e2e1")
        level_label = (
            {
                "DEBUG": "GỠ LỖI", "SYSTEM": "HỆ THỐNG", "INFO": "THÔNG TIN",
                "ACTION": "THAO TÁC", "WARN": "CẢNH BÁO", "WARNING": "CẢNH BÁO",
                "ERROR": "LỖI", "CRITICAL": "NGHIÊM TRỌNG",
            }.get(level_key, level_key)
            if self.language == "vi" else level_key
        )
        safe_msg = html.escape(self._localize_log_message(str(msg))).replace("\n", "<br>")
        html_line = (
            f"<div style='margin-bottom: 2px;'>"
            f"<span style='color: #8a919e;'>[{now_str}]</span> "
            f"<span style='color: {c}; font-weight: bold;'>[{level_label}]</span> "
            f"<span style='color: #e5e2e1;'>{safe_msg}</span></div>"
        )

        self.txt_console.append(html_line)

        if self.chk_autoscroll.isChecked():
            self.txt_console.moveCursor(self.txt_console.textCursor().MoveOperation.End)

    def clear_logs(self):
        self.txt_console.clear()

    @pyqtSlot(str)
    def update_status_display(self, status: str):
        if status.startswith("STARTING"):
            self.lbl_status_val.setText(f"● {status}")
            self.lbl_status_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #fabd00;")
            self.lbl_start_txt.setText(f"[ ⏸ STARTING... ({status}) ]")
        elif status == "RUNNING":
            self.lbl_status_val.setText("● RUNNING")
            self.lbl_status_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #66df75;")
            self.lbl_start_txt.setText("[ ⏸ TẠM DỪNG TỰ ĐỘNG ]" if self.language == "vi" else "[ ⏸ PAUSE AUTOMATION ]")
        elif status == "PAUSED":
            self.lbl_status_val.setText("● PAUSED")
            self.lbl_status_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #fabd00;")
            self.lbl_start_txt.setText("[ ▶ TIẾP TỤC TỰ ĐỘNG ]" if self.language == "vi" else "[ ▶ RESUME AUTOMATION ]")
        else:
            self.lbl_status_val.setText("● STOPPED")
            self.lbl_status_val.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; font-weight: bold; color: #8a919e;")
            self.lbl_start_txt.setText("[ ▶ BẮT ĐẦU TỰ ĐỘNG ]" if self.language == "vi" else "[ ▶ START AUTOMATION ]")

    @pyqtSlot(int)
    def update_templates_count(self, count: int):
        self.lbl_templates_count.setText(str(count))

    def toggle_start_pause(self):
        if not self.worker._running:
            self.worker.start_automation()
        elif self.worker._paused:
            self.worker.resume_automation()
        else:
            self.worker.pause_automation()

    def trigger_emergency_stop(self):
        self._cancel_pending_tool()
        self.worker.stop_automation()
        if not self.isVisible() and not self._overlay_is_up():
            self.show()

    # --- NON-BLOCKING GUI REGION MEASURING ---
    def tool_measure_region(self):
        dlg = MeasureChoiceDialog(self)
        QTimer.singleShot(0, lambda: force_window_foreground(int(dlg.winId()), stay_topmost=True))
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_region:
            self.start_region_overlay(dlg.selected_region)

    def start_region_overlay(self, region_name: str):
        self.hide()
        self._schedule_after_hide(150, lambda: self._launch_overlay(region_name))

    def _launch_overlay(self, region_name: str):
        self._pending_tool_timer = None
        self.active_overlay = GuiRegionOverlay(region_name, main_win=self)
        self.active_overlay.region_selected_signal.connect(self.on_region_measured)
        self.active_overlay.destroyed.connect(self._on_overlay_destroyed)
        self.active_overlay.show()

    def _on_overlay_destroyed(self, *_args):
        self.active_overlay = None
        if not self.isVisible():
            self.show()

    @pyqtSlot(str, int, int, int, int)
    def on_region_measured(self, region_name: str, left: int, top: int, width: int, height: int):
        save_region_to_config(region_name, left, top, width, height)
        msg = f"[✓] Measured & Saved {region_name}: left={left}, top={top}, width={width}, height={height}"
        log_event("SYSTEM", msg)
        self._restore_for_dialog()

    # --- ITEM CAPTURE TOOLS (QUICK HOVER & SCREEN FREEZE) ---
    def start_quick_hover_capture(self, immediate: bool = False):
        if immediate:
            log_event("SYSTEM", "[+] QUICK HOVER CAPTURE: capturing at current cursor position...")
            self.hide()
            self._schedule_after_hide(50, self._perform_quick_hover_crop)
        else:
            log_event("SYSTEM", "[+] QUICK HOVER CAPTURE: Please hover your cursor over the item in game...")
            self.hide()
            self._schedule_after_hide(1500, self._perform_quick_hover_crop)

    def _perform_quick_hover_crop(self):
        self._pending_tool_timer = None
        try:
            cx, cy = pyautogui.position()
            phys_x, phys_y = logical_to_physical_xy(cx, cy)
            full_bgr = grab_primary_monitor_bgr()
            if full_bgr is None:
                raise RuntimeError("Failed to capture the primary monitor.")
            final_crop = trim_yellow_border_if_present(full_bgr, phys_x, phys_y)
            self._restore_for_dialog()
            self.prompt_save_captured_item(final_crop)
        except Exception as e:
            logger.exception(f"Error during quick hover capture: {e}")
            self._restore_for_dialog()

    def start_freeze_capture(self):
        self.hide()
        self._schedule_after_hide(150, self._launch_capture_overlay)

    def _launch_capture_overlay(self):
        self._pending_tool_timer = None
        self.active_overlay = GuiItemCaptureOverlay(main_win=self)
        self.active_overlay.capture_completed_signal.connect(self.on_item_captured)
        self.active_overlay.destroyed.connect(self._on_overlay_destroyed)
        self.active_overlay.show()

    @pyqtSlot(object)
    def on_item_captured(self, crop_bgr):
        # A direct signal is delivered before the overlay's mouse-release
        # handler returns. Close it first so the frozen screenshot is removed
        # before the save dialog is shown.
        overlay = self.active_overlay
        self.active_overlay = None
        if overlay is not None:
            overlay.close()
        self._restore_for_dialog()
        if crop_bgr is not None and getattr(crop_bgr, "size", 0) > 0:
            QTimer.singleShot(0, lambda: self.prompt_save_captured_item(crop_bgr))

    def prompt_save_captured_item(self, crop_bgr: np.ndarray):
        if crop_bgr is None or crop_bgr.size == 0:
            return

        save_dlg = CaptureSaveDialog(crop_bgr, parent=self)
        QTimer.singleShot(0, lambda: force_window_foreground(int(save_dlg.winId()), stay_topmost=True))
        if save_dlg.exec() == QDialog.DialogCode.Accepted and save_dlg.saved_path:
            logger.info(f"[✓] Saved item template: {save_dlg.saved_path}")
            self.tool_reload_templates()

    def tool_reload_templates(self):
        self.worker.reload_templates()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            msg = "Configuration updated via Settings dialog."
            # logger.info(msg)
            self.append_log("INFO", msg)

    # --- DYNAMIC CUSTOMIZABLE HOTKEYS HANDLER ---
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        
        def _matches(hk_name: str) -> bool:
            str_key = config.HOTKEYS.get(hk_name, "")
            return KEY_NAME_TO_QT.get(str_key) == key

        if _matches("START_PAUSE"):
            self.toggle_start_pause()
            event.accept()
        elif _matches("MEASURE_REGION"):
            self.tool_measure_region()
            event.accept()
        elif _matches("QUICK_CAPTURE"):
            self.start_quick_hover_capture()
            event.accept()
        elif _matches("FREEZE_CAPTURE"):
            self.start_freeze_capture()
            event.accept()
        elif _matches("RELOAD_TEMPLATES"):
            self.tool_reload_templates()
            event.accept()
        elif _matches("EMERGENCY_STOP"):
            self.trigger_emergency_stop()
            event.accept()
        else:
            super().keyPressEvent(event)

    # --- WINDOW STATE PERSISTENCE ---
    def load_window_state(self):
        try:
            cfg = config.load_config_json()
            geom = cfg.get("WINDOW_GEOMETRY")
            if geom and isinstance(geom, dict):
                w = max(900, int(geom.get("width", 980)))
                h = max(500, int(geom.get("height", 590)))
                x = int(geom.get("x", 100))
                y = int(geom.get("y", 100))

                screen_ok = False
                for screen in QApplication.screens():
                    if screen.geometry().contains(QPoint(x, y)):
                        screen_ok = True
                        break

                if screen_ok:
                    self.setGeometry(x, y, w, h)
                else:
                    self.resize(w, h)

                if geom.get("maximized", False):
                    self.showMaximized()
        except Exception as e:
            logger.warning(f"Could not restore window state: {e}")

    def save_window_state(self):
        try:
            cfg = config.load_config_json()
            is_max = self.isMaximized()
            normal_geom = self.normalGeometry()
            cfg["WINDOW_GEOMETRY"] = {
                "x": normal_geom.x(),
                "y": normal_geom.y(),
                "width": normal_geom.width(),
                "height": normal_geom.height(),
                "maximized": is_max
            }
            config.save_config_json(cfg)
        except Exception as e:
            logger.warning(f"Could not save window state: {e}")

    def closeEvent(self, event: QCloseEvent):
        self.save_window_state()
        self.hotkeys.stop()
        self.worker.stop_automation()
        self.worker.quit()
        self.worker.wait(1000)
        event.accept()


