"""Dialogs used by the TBH-Tool main window."""
import datetime
import cv2
import numpy as np
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import config
from ui.image_utils import bgr_to_qpixmap
from ui.styles import STITCH_DARK_STYLE

AVAILABLE_HOTKEYS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "Esc"]

class CaptureSaveDialog(QDialog):
    def __init__(self, crop_bgr: np.ndarray, parent=None):
        super().__init__(parent)
        self.crop_bgr = crop_bgr
        self.saved_path = None
        self.is_vietnamese = getattr(parent, "language", "vi") == "vi"
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(460)
        self.init_ui()
        self.adjustSize()
        self.resize(max(460, self.sizeHint().width()), self.sizeHint().height())
        self._drag_pos = None
        QApplication.instance().installEventFilter(self)

    def init_ui(self):
        text = (
            {
                "title": "LƯU MẪU VẬT PHẨM", "size": "Kích thước hình:\n{} x {} px",
                "empty": "Không có dữ liệu hình ảnh", "folder": "Thư mục lưu:",
                "filename": "Tên tệp mẫu (.png):", "cancel": "Hủy", "save": "Lưu mẫu",
                "invalid_title": "Tên không hợp lệ", "invalid_body": "Hãy nhập tên tệp mẫu hợp lệ.",
            }
            if self.is_vietnamese else
            {
                "title": "SAVE ITEM TEMPLATE", "size": "Graphic Size:\n{} x {} px",
                "empty": "No Graphic Data", "folder": "Target Folder Category:",
                "filename": "Template Filename (.png):", "cancel": "Cancel", "save": "Save Template",
                "invalid_title": "Invalid Name", "invalid_body": "Please enter a valid template filename.",
            }
        )
        self._text = text
        self.setStyleSheet(STITCH_DARK_STYLE)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color: #1b1b1c; border-bottom: 1px solid #404752;")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(12, 8, 12, 8)

        lbl_title = QLabel(text["title"])
        lbl_title.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: bold; font-size: 11px; color: #66df75;")

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("background: transparent; border: none; color: #c0c7d4; font-weight: bold;")
        btn_close.clicked.connect(self.reject)

        header_lay.addWidget(lbl_title)
        header_lay.addStretch()
        header_lay.addWidget(btn_close)
        main_layout.addWidget(header)

        body = QWidget()
        body.setStyleSheet("background-color: #131313;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(16, 16, 16, 16)
        body_lay.setSpacing(12)

        prev_box = QFrame()
        prev_box.setStyleSheet("background-color: #0e0e0e; border: 1px solid #404752; border-radius: 4px; padding: 8px;")
        prev_lay = QHBoxLayout(prev_box)
        prev_lay.setContentsMargins(0, 0, 0, 0)

        lbl_img = QLabel()
        if self.crop_bgr is not None and self.crop_bgr.size > 0:
            pix = bgr_to_qpixmap(self.crop_bgr)
            h, w = self.crop_bgr.shape[:2]
            if pix is not None:
                lbl_img.setPixmap(pix.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl_info = QLabel(text["size"].format(w, h))
            lbl_info.setStyleSheet("font-family: 'JetBrains Mono'; font-size: 11px; color: #a3c9ff;")
        else:
            lbl_info = QLabel(text["empty"])

        prev_lay.addStretch()
        prev_lay.addWidget(lbl_img)
        prev_lay.addSpacing(16)
        prev_lay.addWidget(lbl_info)
        prev_lay.addStretch()
        body_lay.addWidget(prev_box)

        body_lay.addWidget(QLabel(text["folder"]))
        self.cmb_folder = QComboBox()
        self.cmb_folder.addItems(["sell_items", "stash_items"])
        body_lay.addWidget(self.cmb_folder)

        body_lay.addWidget(QLabel(text["filename"]))
        default_name = f"item_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        self.txt_filename = QLineEdit(default_name)
        self.txt_filename.returnPressed.connect(self.save_template)
        body_lay.addWidget(self.txt_filename)

        main_layout.addWidget(body)

        footer = QFrame()
        footer.setStyleSheet("background-color: #1b1b1c; border-top: 1px solid #404752;")
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(12, 10, 12, 10)

        btn_cancel = QPushButton(text["cancel"])
        btn_cancel.setObjectName("ToolBtn")
        btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton(text["save"])
        self.btn_save.setDefault(True)
        self.btn_save.setStyleSheet("background-color: #27a644; border: none; border-radius: 4px; color: #ffffff; font-weight: bold; padding: 6px 16px;")
        self.btn_save.clicked.connect(self.save_template)

        footer_lay.addStretch()
        footer_lay.addWidget(btn_cancel)
        footer_lay.addWidget(self.btn_save)
        main_layout.addWidget(footer)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def save_template(self):
        cat = self.cmb_folder.currentText()
        fname = self.txt_filename.text().strip()
        if not fname:
            QMessageBox.warning(self, self._text["invalid_title"], self._text["invalid_body"])
            return

        if not fname.endswith(".png"):
            fname += ".png"

        target_dir = config.SELL_ITEMS_DIR if cat == "sell_items" else config.STASH_ITEMS_DIR
        target_path = target_dir / fname

        cv2.imwrite(str(target_path), self.crop_bgr)
        self.saved_path = f"templates/{cat}/{fname}"
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.save_template()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and self.isVisible()
            and self.isActiveWindow()
        ):
            self.save_template()
            return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)



class MeasureChoiceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_vietnamese = getattr(parent, "language", "vi") == "vi"
        self.setWindowTitle("Chọn vùng cần đo" if self.is_vietnamese else "Select Region to Measure")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(460)
        self.selected_region = None
        self.init_ui()
        self.adjustSize()
        self.resize(max(460, self.sizeHint().width()), self.sizeHint().height())
        self._drag_pos = None

    def init_ui(self):
        self.setStyleSheet(STITCH_DARK_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color: #1b1b1c; border-bottom: 1px solid #404752;")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(12, 8, 12, 8)

        lbl_title = QLabel("ĐO VÙNG MÀN HÌNH" if self.is_vietnamese else "MEASURE REGION")
        lbl_title.setStyleSheet("font-family: 'JetBrains Mono'; font-weight: bold; font-size: 11px; color: #a3c9ff;")

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("background: transparent; border: none; color: #c0c7d4; font-weight: bold;")
        btn_close.clicked.connect(self.reject)

        header_lay.addWidget(lbl_title)
        header_lay.addStretch()
        header_lay.addWidget(btn_close)
        layout.addWidget(header)

        body = QWidget()
        body.setStyleSheet("background-color: #131313;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(16, 16, 16, 16)
        body_lay.setSpacing(12)

        lbl = QLabel("Bạn muốn đo vùng nào?" if self.is_vietnamese else "Which region would you like to measure?")
        lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #e5e2e1;")
        body_lay.addWidget(lbl)

        btn_inv = QPushButton("🎒 Đo vùng túi đồ" if self.is_vietnamese else "🎒 Measure Inventory Region")
        btn_inv.setObjectName("ToolBtn")
        btn_inv.setStyleSheet("padding: 10px; font-weight: bold;")
        btn_inv.clicked.connect(self.select_inventory)
        body_lay.addWidget(btn_inv)

        btn_game = QPushButton("🎮 Đo vùng cửa sổ game" if self.is_vietnamese else "🎮 Measure Game Window Region")
        btn_game.setObjectName("ToolBtn")
        btn_game.setStyleSheet("padding: 10px; font-weight: bold;")
        btn_game.clicked.connect(self.select_game)
        body_lay.addWidget(btn_game)

        layout.addWidget(body)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def select_inventory(self):
        self.selected_region = "INVENTORY_REGION"
        self.accept()

    def select_game(self):
        self.selected_region = "GAME_REGION"
        self.accept()


# --- SETTINGS MODAL DIALOG WITH CUSTOMIZABLE HOTKEYS ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.language = getattr(parent, "language", "vi")
        self.setWindowTitle("Utility Settings - TBH-Tool v2.0")
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.setMinimumWidth(960)
        self.setModal(True)
        self.init_ui()
        self.retranslate_ui()
        self.adjustSize()
        needed_h = max(self.sizeHint().height(), self.minimumSizeHint().height())
        self.setMinimumHeight(needed_h)
        self.resize(max(960, self.sizeHint().width()), needed_h)
        self._drag_pos = None

    def retranslate_ui(self):
        if self.language != "vi":
            return

        self.setWindowTitle("Cài đặt tiện ích - TBH-Tool v2.0")
        translations = {
            "UTILITY SETTINGS": "CÀI ĐẶT TIỆN ÍCH",
            "AUTOMATION": "TỰ ĐỘNG HÓA",
            "Confidence Threshold:": "Ngưỡng độ tin cậy:",
            "Scan Interval (s):": "Chu kỳ quét (giây):",
            "Click Duration:": "Thời gian nhấp:",
            "Random Delay (s):": "Độ trễ ngẫu nhiên (giây):",
            "Cooldown interval:": "Khoảng chờ:",
            "Sales Slots Capacity:": "Số ô bán tối đa:",
            "REGIONS": "VÙNG MÀN HÌNH",
            "Measure Game Region": "Đo vùng game",
            "Measure Inventory Region": "Đo vùng túi đồ",
            "INVENTORY SCROLL": "CUỘN TÚI ĐỒ",
            "Enable Smart Inventory Scroll": "Bật cuộn túi đồ thông minh",
            "Max Scroll Steps:": "Số bước cuộn tối đa:",
            "Scroll Ticks/Step:": "Nấc cuộn mỗi bước:",
            "INPUT SETTINGS": "CÀI ĐẶT THAO TÁC",
            "Stash Modifier:": "Phím bổ trợ cất kho:",
            "Sell Modifier:": "Phím bổ trợ bán:",
            "Mouse Button:": "Nút chuột:",
            "CUSTOMIZABLE HOTKEYS": "PHÍM TẮT TÙY CHỈNH",
            "Start / Pause": "Bắt đầu / Tạm dừng",
            "Measure Region": "Đo vùng màn hình",
            "Quick Capture": "Chụp nhanh",
            "Freeze Snipper": "Cắt ảnh đóng băng",
            "Reload Templates": "Tải lại mẫu",
            "Emergency Stop": "Dừng khẩn cấp",
            "SAFETY": "AN TOÀN",
            "PyAutoGUI Failsafe (0,0 Corner)": "Dừng an toàn PyAutoGUI (góc 0,0)",
            "Cancel": "Hủy",
            "Save Changes": "Lưu thay đổi",
        }
        for widget_type in (QLabel, QPushButton, QCheckBox):
            for widget in self.findChildren(widget_type):
                if widget.text() in translations:
                    widget.setText(translations[widget.text()])
                elif isinstance(widget, QLabel) and widget.text().startswith("Shortcuts work only"):
                    widget.setText(
                        "Phím tắt chỉ hoạt động khi công cụ này, màn hình nền hoặc TaskBarHero đang được chọn — "
                        "không hoạt động trong Chrome, Cài đặt hoặc File Explorer. Esc vẫn hủy lớp phủ đo/chụp."
                    )

    def init_ui(self):
        self.setStyleSheet(STITCH_DARK_STYLE)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        body = QWidget()
        body.setStyleSheet("background-color: #131313;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)

        # --- Col 1: Automation & Regions ---
        col1 = QVBoxLayout()
        lbl_sec1 = QLabel("AUTOMATION")
        lbl_sec1.setStyleSheet("font-weight: bold; font-size: 10px; color: #a3c9ff; border-bottom: 1px solid rgba(163,201,255,0.2); padding-bottom: 3px;")
        col1.addWidget(lbl_sec1)

        f1 = QHBoxLayout()
        f1.addWidget(QLabel("Confidence Threshold:"))
        self.txt_confidence = QLineEdit(str(config.CONFIDENCE_THRESHOLD))
        self.txt_confidence.setFixedWidth(60)
        f1.addWidget(self.txt_confidence)
        col1.addLayout(f1)

        f2 = QHBoxLayout()
        f2.addWidget(QLabel("Scan Interval (s):"))
        self.txt_interval = QLineEdit(str(config.SCAN_INTERVAL))
        self.txt_interval.setFixedWidth(60)
        f2.addWidget(self.txt_interval)
        col1.addLayout(f2)

        f3 = QHBoxLayout()
        f3.addWidget(QLabel("Click Duration:"))
        self.txt_click_duration = QLineEdit(str(config.CLICK_DURATION))
        self.txt_click_duration.setFixedWidth(60)
        f3.addWidget(self.txt_click_duration)
        col1.addLayout(f3)

        f4 = QHBoxLayout()
        f4.addWidget(QLabel("Random Delay (s):"))
        self.txt_random_delay_min = QLineEdit(str(config.RANDOM_DELAY[0]))
        self.txt_random_delay_min.setFixedWidth(60)
        f4.addWidget(self.txt_random_delay_min)
        f4.addWidget(QLabel("~"))
        self.txt_random_delay_max = QLineEdit(str(config.RANDOM_DELAY[1]))
        self.txt_random_delay_max.setFixedWidth(60)
        f4.addWidget(self.txt_random_delay_max)
        col1.addLayout(f4)

        f5 = QHBoxLayout()
        f5.addWidget(QLabel("Cooldown interval:"))
        self.txt_cooldown_interval = QLineEdit(str(config.COOLDOWN_INTERVAL))
        self.txt_cooldown_interval.setFixedWidth(60)
        f5.addWidget(self.txt_cooldown_interval)
        col1.addLayout(f5)

        f6 = QHBoxLayout()
        f6.addWidget(QLabel("Sales Slots Capacity:"))
        self.txt_capacity = QLineEdit(str(config.SALES_SLOTS_CAPACITY))
        self.txt_capacity.setFixedWidth(60)
        f6.addWidget(self.txt_capacity)
        col1.addLayout(f6)

        lbl_sec2 = QLabel("REGIONS")
        lbl_sec2.setStyleSheet("font-weight: bold; font-size: 10px; color: #a3c9ff; border-bottom: 1px solid rgba(163,201,255,0.2); padding-bottom: 3px; margin-top: 10px;")
        col1.addWidget(lbl_sec2)

        btn_meas_game = QPushButton("Measure Game Region")
        btn_meas_game.setObjectName("ToolBtn")
        btn_meas_game.clicked.connect(self.measure_game_region)
        col1.addWidget(btn_meas_game)

        btn_meas_inv = QPushButton("Measure Inventory Region")
        btn_meas_inv.setObjectName("ToolBtn")
        btn_meas_inv.clicked.connect(self.measure_inventory_region)
        col1.addWidget(btn_meas_inv)

        col1.addStretch()
        body_layout.addLayout(col1)

        # --- Col 2: Inventory & Input ---
        col2 = QVBoxLayout()
        lbl_sec3 = QLabel("INVENTORY SCROLL")
        lbl_sec3.setStyleSheet("font-weight: bold; font-size: 10px; color: #a3c9ff; border-bottom: 1px solid rgba(163,201,255,0.2); padding-bottom: 3px;")
        col2.addWidget(lbl_sec3)

        self.chk_scroll = QCheckBox("Enable Smart Inventory Scroll")
        self.chk_scroll.setChecked(config.INVENTORY_SCROLL_ENABLED)
        col2.addWidget(self.chk_scroll)

        f7 = QHBoxLayout()
        f7.addWidget(QLabel("Max Scroll Steps:"))
        self.txt_scroll_max = QLineEdit(str(config.INVENTORY_SCROLL_MAX_STEPS))
        self.txt_scroll_max.setFixedWidth(50)
        f7.addWidget(self.txt_scroll_max)
        col2.addLayout(f7)

        f_ticks = QHBoxLayout()
        f_ticks.addWidget(QLabel("Scroll Ticks/Step:"))
        self.txt_scroll_ticks = QLineEdit(str(config.INVENTORY_SCROLL_TICKS))
        self.txt_scroll_ticks.setFixedWidth(50)
        f_ticks.addWidget(self.txt_scroll_ticks)
        col2.addLayout(f_ticks)

        lbl_sec4 = QLabel("INPUT SETTINGS")
        lbl_sec4.setStyleSheet("font-weight: bold; font-size: 10px; color: #a3c9ff; border-bottom: 1px solid rgba(163,201,255,0.2); padding-bottom: 3px; margin-top: 10px;")
        col2.addWidget(lbl_sec4)

        f8 = QHBoxLayout()
        f8.addWidget(QLabel("Stash Modifier:"))
        self.cmb_stash_mod = QComboBox()
        self.cmb_stash_mod.addItems(["ctrl", "alt", "shift"])
        self.cmb_stash_mod.setCurrentText(config.STASH_MODIFIER.lower())
        f8.addWidget(self.cmb_stash_mod)
        col2.addLayout(f8)

        f9 = QHBoxLayout()
        f9.addWidget(QLabel("Sell Modifier:"))
        self.cmb_sell_mod = QComboBox()
        self.cmb_sell_mod.addItems(["alt", "ctrl", "shift"])
        self.cmb_sell_mod.setCurrentText(config.SELL_MODIFIER.lower())
        f9.addWidget(self.cmb_sell_mod)
        col2.addLayout(f9)

        f10 = QHBoxLayout()
        f10.addWidget(QLabel("Mouse Button:"))
        self.cmb_mouse_btn = QComboBox()
        self.cmb_mouse_btn.addItems(["right", "left"])
        self.cmb_mouse_btn.setCurrentText(config.ITEM_MOUSE_BUTTON.lower())
        f10.addWidget(self.cmb_mouse_btn)
        col2.addLayout(f10)

        col2.addStretch()
        body_layout.addLayout(col2)

        # --- Col 3: Customizable Hotkeys & Safety ---
        col3 = QVBoxLayout()
        lbl_sec5 = QLabel("CUSTOMIZABLE HOTKEYS")
        lbl_sec5.setStyleSheet("font-weight: bold; font-size: 10px; color: #a3c9ff; border-bottom: 1px solid rgba(163,201,255,0.2); padding-bottom: 3px;")
        col3.addWidget(lbl_sec5)

        hk_frame = QFrame()
        hk_frame.setStyleSheet("background-color: #1b1b1c; border: 1px solid #404752; border-radius: 3px; padding: 6px;")
        hk_layout = QVBoxLayout(hk_frame)
        hk_layout.setSpacing(6)

        self.hk_combos = {}
        hotkey_labels = [
            ("START_PAUSE", "Start / Pause"),
            ("MEASURE_REGION", "Measure Region"),
            ("QUICK_CAPTURE", "Quick Capture"),
            ("FREEZE_CAPTURE", "Freeze Snipper"),
            ("RELOAD_TEMPLATES", "Reload Templates"),
            ("EMERGENCY_STOP", "Emergency Stop"),
        ]

        for hk_key, hk_desc in hotkey_labels:
            row = QHBoxLayout()
            lbl_v = QLabel(hk_desc)
            lbl_v.setStyleSheet("color: #c0c7d4; font-size: 11px;")
            
            cmb_k = QComboBox()
            cmb_k.setFixedWidth(70)
            cmb_k.addItems(AVAILABLE_HOTKEYS)
            cur_val = config.HOTKEYS.get(hk_key, "F1")
            if cur_val in AVAILABLE_HOTKEYS:
                cmb_k.setCurrentText(cur_val)
            else:
                cmb_k.setCurrentText("F1")

            row.addWidget(lbl_v)
            row.addStretch()
            row.addWidget(cmb_k)
            hk_layout.addLayout(row)
            self.hk_combos[hk_key] = cmb_k

        col3.addWidget(hk_frame)

        lbl_hk_hint = QLabel("Shortcuts work only while this tool, the desktop, or TaskBarHero is focused — not in Chrome, Settings, or File Explorer. Esc still cancels Measure / Capture overlays.")
        lbl_hk_hint.setWordWrap(True)
        lbl_hk_hint.setStyleSheet("font-size: 10px; color: #8a919e;")
        col3.addWidget(lbl_hk_hint)

        lbl_sec6 = QLabel("SAFETY")
        lbl_sec6.setStyleSheet("font-weight: bold; font-size: 10px; color: #ffb4ab; border-bottom: 1px solid rgba(255,180,171,0.2); padding-bottom: 3px; margin-top: 10px;")
        col3.addWidget(lbl_sec6)

        self.chk_failsafe = QCheckBox("PyAutoGUI Failsafe (0,0 Corner)")
        self.chk_failsafe.setChecked(config.FAILSAFE)
        col3.addWidget(self.chk_failsafe)

        col3.addStretch()
        body_layout.addLayout(col3)

        main_layout.addWidget(body)

        footer = QFrame()
        footer.setStyleSheet("background-color: #1b1b1c; border-top: 1px solid #404752;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 10, 12, 10)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("ToolBtn")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet("background-color: #0078d4; border: none; border-radius: 4px; color: #ffffff; font-weight: bold; padding: 6px 16px;")
        btn_save.clicked.connect(self.save_settings)

        footer_layout.addStretch()
        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_save)
        main_layout.addWidget(footer)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def measure_game_region(self):
        if self.parent() and hasattr(self.parent(), "start_region_overlay"):
            self.hide()
            self.parent().start_region_overlay("GAME_REGION")
            self.show()

    def measure_inventory_region(self):
        if self.parent() and hasattr(self.parent(), "start_region_overlay"):
            self.hide()
            self.parent().start_region_overlay("INVENTORY_REGION")
            self.show()

    def save_settings(self):
        try:
            conf = float(self.txt_confidence.text().strip())
            interval = float(self.txt_interval.text().strip())
            duration = float(self.txt_click_duration.text().strip())
            random_delay_min = float(self.txt_random_delay_min.text().strip())
            random_delay_max = float(self.txt_random_delay_max.text().strip())
            cooldown_interval = float(self.txt_cooldown_interval.text().strip())
            capacity = int(self.txt_capacity.text().strip())
            s_max = int(self.txt_scroll_max.text().strip())
            s_ticks = int(self.txt_scroll_ticks.text().strip())

            new_hotkeys = {}
            for hk_key, cmb in self.hk_combos.items():
                new_hotkeys[hk_key] = cmb.currentText()

            assigned = list(new_hotkeys.values())
            if len(assigned) != len(set(assigned)):
                QMessageBox.warning(self, "Duplicate Hotkeys", "Each action must use a different key.")
                return

            config.update_setting("CONFIDENCE_THRESHOLD", conf)
            config.update_setting("SCAN_INTERVAL", interval)
            config.update_setting("CLICK_DURATION", duration)
            config.update_setting("RANDOM_DELAY", [random_delay_min, random_delay_max])
            config.update_setting("COOLDOWN_INTERVAL", cooldown_interval)
            config.update_setting("SALES_SLOTS_CAPACITY", capacity)
            config.update_setting("INVENTORY_SCROLL_ENABLED", self.chk_scroll.isChecked())
            config.update_setting("INVENTORY_SCROLL_MAX_STEPS", s_max)
            config.update_setting("INVENTORY_SCROLL_TICKS", s_ticks)
            config.update_setting("STASH_MODIFIER", self.cmb_stash_mod.currentText())
            config.update_setting("SELL_MODIFIER", self.cmb_sell_mod.currentText())
            config.update_setting("ITEM_MOUSE_BUTTON", self.cmb_mouse_btn.currentText())
            config.update_setting("FAILSAFE", self.chk_failsafe.isChecked())
            config.update_setting("HOTKEYS", new_hotkeys)

            if self.parent() and hasattr(self.parent(), "reload_global_hotkeys"):
                self.parent().reload_global_hotkeys()
            elif self.parent() and hasattr(self.parent(), "update_hotkey_badges"):
                self.parent().update_hotkey_badges()

            self.accept()
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Please enter valid numeric values: {e}")


# --- MAIN APPLICATION WINDOW ---
