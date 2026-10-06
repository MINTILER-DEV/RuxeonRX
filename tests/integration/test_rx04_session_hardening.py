import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RXCTL = ROOT / "tools" / "rxctl"


class RX04SessionHardeningTest(unittest.TestCase):
    def command(self, state: Path, *arguments: str) -> object:
        completed = subprocess.run([sys.executable, str(RXCTL), "--state", str(state), *arguments], check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)

    def test_session_health_safe_mode_recovery_settings_and_devices(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            session = self.command(state, "session-start")
            self.assertEqual("normal", session["mode"])
            self.assertTrue(self.command(state, "session-health")["healthy"])
            for _ in range(3):
                crashed = self.command(state, "session-crash", "rx-appd")
            self.assertEqual("safe", crashed["mode"])
            self.assertFalse(self.command(state, "session-health")["healthy"])
            recovered = self.command(state, "session-recover")
            self.assertEqual("normal", recovered["mode"])
            self.assertTrue(self.command(state, "session-health")["healthy"])
            settings = self.command(state, "set", "appearance.high_contrast", "true")
            self.assertTrue(settings["appearance.high_contrast"])
            scaled = self.command(state, "set", "appearance.text_scale", "1.5")
            self.assertEqual(1.5, scaled["appearance.text_scale"])
            devices = self.command(state, "devices")
            self.assertIn("architecture", devices)
            self.assertIn("virtualization", devices)
