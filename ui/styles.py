"""Shared stylesheet definitions for PyQt views."""

# --- STITCH AI DARK THEME STYLESHEET ---
STITCH_DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #131313;
    color: #e5e2e1;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e5e2e1;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

QFrame#HeaderFrame {
    background-color: #1b1b1c;
    border-bottom: 1px solid #404752;
}

QFrame#PanelContainer {
    background-color: #202020;
    border: 1px solid #404752;
    border-radius: 4px;
}

QFrame#ConsoleContainer {
    background-color: #0e0e0e;
    border: 1px solid #404752;
    border-radius: 4px;
}

/* Primary Action Buttons */
QPushButton#StartBtn {
    background-color: rgba(39, 166, 68, 0.15);
    border: 1px solid #27a644;
    border-radius: 4px;
    color: #66df75;
    font-weight: bold;
    font-size: 15px;
    padding: 14px 18px;
    text-align: left;
}
QPushButton#StartBtn:hover {
    background-color: rgba(39, 166, 68, 0.28);
    border-color: #66df75;
}
QPushButton#StartBtn:pressed {
    background-color: rgba(39, 166, 68, 0.40);
}

QPushButton#StopBtn {
    background-color: rgba(147, 0, 10, 0.20);
    border: 1px solid #93000a;
    border-radius: 4px;
    color: #ffb4ab;
    font-weight: bold;
    font-size: 15px;
    padding: 14px 18px;
    text-align: left;
}
QPushButton#StopBtn:hover {
    background-color: #93000a;
    color: #ffffff;
}
QPushButton#StopBtn:pressed {
    background-color: #690005;
}

/* Secondary Tool Buttons */
QPushButton#ToolBtn {
    background-color: #202020;
    border: 1px solid #404752;
    border-radius: 4px;
    color: #e5e2e1;
    font-weight: 600;
    font-size: 12px;
    padding: 8px 10px;
}
QPushButton#ToolBtn:hover {
    background-color: #2a2a2a;
    border-color: #a3c9ff;
    color: #ffffff;
}
QPushButton#ToolBtn:pressed {
    background-color: #353535;
}

/* Settings & Header Buttons */
QPushButton#SettingsBtn {
    background-color: transparent;
    border: none;
    border-left: 1px solid rgba(64, 71, 82, 0.6);
    color: #c0c7d4;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    font-weight: bold;
    padding: 0px 12px;
}
QPushButton#SettingsBtn:hover {
    background-color: #353535;
    color: #ffffff;
}

QPushButton#WindowControlBtn {
    background-color: transparent;
    border: none;
    color: #c0c7d4;
    font-size: 13px;
    font-weight: bold;
    padding: 0px 10px;
}
QPushButton#WindowControlBtn:hover {
    background-color: #353535;
    color: #ffffff;
}
QPushButton#WindowCloseBtn {
    background-color: transparent;
    border: none;
    color: #c0c7d4;
    font-size: 14px;
    font-weight: bold;
    padding: 0px 12px;
}
QPushButton#WindowCloseBtn:hover {
    background-color: #93000a;
    color: #ffffff;
}

/* Inputs & Combo Boxes */
QLineEdit, QComboBox {
    background-color: #131313;
    border: 1px solid #404752;
    border-radius: 3px;
    color: #e5e2e1;
    padding: 4px 8px;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #0078d4;
}

QCheckBox {
    color: #c0c7d4;
    font-size: 11px;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    background-color: #131313;
    border: 1px solid #404752;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

/* Console Log View */
QTextEdit#LogConsole {
    background-color: #0e0e0e;
    border: none;
    color: #c0c7d4;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    line-height: 1.4;
}

/* Key Badges */
QLabel#KbdBadge {
    background-color: #131313;
    border: 1px solid #404752;
    border-radius: 3px;
    color: #66df75;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-weight: bold;
    font-size: 11px;
    padding: 2px 6px;
}
QLabel#KbdBadgeEsc {
    background-color: rgba(147, 0, 10, 0.3);
    border: 1px solid #93000a;
    border-radius: 3px;
    color: #ffb4ab;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-weight: bold;
    font-size: 11px;
    padding: 2px 6px;
}
QLabel#KbdBadgeTool {
    background-color: #131313;
    border: 1px solid rgba(64, 71, 82, 0.5);
    border-radius: 3px;
    color: #c0c7d4;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 10px;
    padding: 1px 5px;
}
"""
