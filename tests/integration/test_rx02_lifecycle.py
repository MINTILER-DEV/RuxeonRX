import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RXCTL = ROOT / "tools" / "rxctl"
MANIFEST = ROOT / "packages" / "native-test-app" / "manifest.json"


class RX02LifecycleTest(unittest.TestCase):
    def command(self, state: Path, *arguments: str) -> object:
        completed = subprocess.run([sys.executable, str(RXCTL), "--state", str(state), *arguments], check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)

    def test_native_app_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            app = self.command(state, "install", str(MANIFEST))
            app_id = app["id"]
            self.assertEqual([app_id], [item["id"] for item in self.command(state, "apps", "--query", "native")])
            self.assertEqual(["rx-native-test-app"], self.command(state, "launch", app_id)["command"])
            self.assertFalse(self.command(state, "notify", app_id, "Hello", "blocked")["delivered"])
            self.command(state, "decide", app_id, "notifications", "allow")
            self.assertTrue(self.command(state, "notify", app_id, "Hello", "shown")["delivered"])
            details = self.command(state, "inspect", app_id)
            self.assertEqual(1, details["app"]["launch_count"])
            self.assertTrue(details["permissions"]["notifications"])
            self.assertIn("launch requested: rx-native-test-app", details["logs"])
            self.assertTrue(self.command(state, "remove", app_id, "--purge-data")["removed"])
            self.assertEqual([], self.command(state, "apps"))
            self.assertEqual([], self.command(state, "notifications"))
