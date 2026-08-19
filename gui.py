"""Compatibility facade for the modular PyQt6 UI package."""
from app.automation_worker import AutomationWorker
from ui.application import run_gui_app
from ui.dialogs import CaptureSaveDialog, MeasureChoiceDialog, SettingsDialog
from ui.main_window import TBHToolMainWindow
from ui.overlays import FrozenScreenOverlay, GuiItemCaptureOverlay, GuiRegionOverlay, OverlayEscFilter

__all__ = [
    "AutomationWorker", "CaptureSaveDialog", "FrozenScreenOverlay",
    "GuiItemCaptureOverlay", "GuiRegionOverlay", "MeasureChoiceDialog",
    "OverlayEscFilter", "SettingsDialog", "TBHToolMainWindow", "run_gui_app",
]

if __name__ == "__main__":
    run_gui_app()
