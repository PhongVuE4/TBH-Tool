"""Smoke tests for each extracted dialog's required Qt dependencies."""

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication

from ui.dialogs import CaptureSaveDialog, MeasureChoiceDialog, SettingsDialog


class DialogConstructionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialogs_construct_without_missing_widget_dependencies(self):
        dialogs = [
            CaptureSaveDialog(np.zeros((8, 8, 3), dtype=np.uint8)),
            MeasureChoiceDialog(),
            SettingsDialog(),
        ]
        for dialog in dialogs:
            dialog.close()
