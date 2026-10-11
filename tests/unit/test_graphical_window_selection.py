"""Regression coverage for actual GTK leader/minimized-window observations."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "e2e/guest_desktop.py"
spec = importlib.util.spec_from_file_location("guest_window_checks", path)
guest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guest)


class GraphicalWindowSelection(unittest.TestCase):
    @patch.object(guest.subprocess, "check_output")
    def test_application_leader_is_not_a_user_window(self, output):
        output.side_effect = ["WM_STATE: not found.\n_NET_WM_STATE: not found.", "WM_STATE(WM_STATE):\nwindow state: Normal\n_NET_WM_STATE(ATOM) ="]
        self.assertEqual(guest.managed_window("101\n102\n"), "102")

    @patch.object(guest.subprocess, "check_output")
    def test_minimized_window_and_its_mapped_leader_are_not_visible(self, output):
        output.side_effect = ["window state: Iconic\n_NET_WM_STATE(ATOM) = _NET_WM_STATE_HIDDEN", "WM_STATE: not found."]
        self.assertIsNone(guest.managed_window("201 202"))

    @patch.object(guest.subprocess, "check_output")
    def test_hidden_state_is_rejected_even_when_normal_state_lags(self, output):
        output.return_value = "window state: Normal\n_NET_WM_STATE(ATOM) = _NET_WM_STATE_HIDDEN"
        self.assertIsNone(guest.managed_window("301"))
