"""Regression tests for immediate automation cancellation."""

from threading import Event
from unittest import TestCase
from unittest.mock import patch

from automation import AutomationEngine


class AutomationInterruptTests(TestCase):
    def make_engine(self) -> AutomationEngine:
        engine = AutomationEngine.__new__(AutomationEngine)
        engine._interrupt_event = Event()
        engine.validate_coordinates = lambda _x, _y: True
        engine.sanitize_modifier_keys = lambda: None
        return engine

    def test_interrupt_prevents_queued_click(self):
        engine = self.make_engine()
        engine.set_interrupted(True)

        with patch("automation.pyautogui.moveTo") as move_to, patch(
            "automation.pyautogui.click"
        ) as click:
            self.assertFalse(engine._move_and_click(100, 100))

        move_to.assert_not_called()
        click.assert_not_called()

    def test_wait_returns_immediately_when_interrupted(self):
        engine = self.make_engine()
        engine.set_interrupted(True)

        self.assertFalse(engine.wait(5.0))
