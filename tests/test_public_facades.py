"""Public launch modules remain stable while implementation modules evolve."""

from unittest import TestCase

import gui
import main


class PublicFacadeTests(TestCase):
    def test_main_exposes_legacy_automation_api(self):
        self.assertTrue(callable(main.main))
        self.assertTrue(callable(main.process_match))
        self.assertTrue(callable(main.ensure_ui_tabs_ready))

    def test_gui_exposes_legacy_gui_api(self):
        self.assertTrue(callable(gui.run_gui_app))
        self.assertIsNotNone(gui.TBHToolMainWindow)
        self.assertIsNotNone(gui.AutomationWorker)
