"""PyQt application bootstrap."""

import sys

from PyQt6.QtCore import QDir, QLockFile, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.main_window import TBHToolMainWindow
from utils import install_error_logging_hooks


def run_gui_app() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("TBH-Tool v2.0")
    install_error_logging_hooks()

    lock_file = QLockFile(QDir.tempPath() + "/tbh_tool_v2.lock")
    if not lock_file.tryLock(100):
        QMessageBox.warning(None, "Already Running", "Another instance of TBH-Tool is already running!")
        return

    main_window = TBHToolMainWindow()
    main_window.show()
    sys.exit(app.exec())
