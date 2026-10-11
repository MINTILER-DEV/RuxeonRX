"""Regression coverage for actual GTK leader/minimized-window observations."""
import importlib.util
from pathlib import Path
import unittest
import sys
from unittest.mock import patch, Mock, call
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / "e2e/guest_desktop.py"
sys.path.insert(0, str(path.parents[2] / "sdk/bindings/python"))
spec = importlib.util.spec_from_file_location("guest_window_checks", path)
guest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guest)
sys.path.insert(0, str(path.parent))
beta_spec = importlib.util.spec_from_file_location("guest_beta_checks", path.parent / "guest_beta.py")
beta = importlib.util.module_from_spec(beta_spec)
beta_spec.loader.exec_module(beta)


class GraphicalWindowSelection(unittest.TestCase):
    def test_nested_adwaita_controls_are_not_cut_off_at_eighteen_levels(self):
        leaf = SimpleNamespace(name="Restore")
        tree = [leaf]
        for unused in range(24): tree = [tree]
        self.assertIn(leaf, list(beta.descendants(tree)))

    def test_unsupported_entry_focus_uses_real_window_relative_pointer_coordinates(self):
        node = Mock(); node.name = "Snapshot name"; node.getRoleName.return_value = "entry"
        frame = Mock(); frame.name = "RX Recovery"; frame.parent = None; node.parent = frame
        node.queryComponent.return_value.grabFocus.side_effect = RuntimeError("GTK focus unsupported")
        node.queryComponent.return_value.getExtents.return_value = SimpleNamespace(x=1, y=2, width=10, height=10)
        with patch.object(beta, "wait", return_value=node), patch.object(beta, "window", side_effect=lambda title: "501" if title == "RX Recovery" else None), patch.object(beta, "xdo", return_value="") as xdo, patch.object(beta.subprocess, "check_output", return_value="Absolute upper-left X: 100\nAbsolute upper-left Y: 200\n"), patch("builtins.print"):
            beta.click(SimpleNamespace(WINDOW_COORDS=1), "Snapshot name")
        xdo.assert_has_calls([call("windowactivate", "--sync", "501"), call("mousemove", "106", "207"), call("click", "1")])

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
