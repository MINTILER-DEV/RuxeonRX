import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RXCTL = ROOT / "tools" / "rxctl"
MANIFEST = ROOT / "packages" / "native-test-app" / "manifest.json"


class RX05AlphaRecoveryTest(unittest.TestCase):
    def command(self, state: Path, *arguments: str) -> object:
        completed = subprocess.run([sys.executable, str(RXCTL), "--state", str(state), *arguments], check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)

    def test_snapshot_restore_and_scrubbed_support_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            app_id = self.command(state, "install", str(MANIFEST))["id"]
            self.command(state, "session-start")
            self.command(state, "set", "privacy.telemetry", "false")
            snapshot = self.command(state, "snapshot", "known-good")
            self.assertTrue(Path(snapshot["snapshot"]).is_file())
            self.command(state, "set", "privacy.telemetry", "true")
            self.command(state, "restore", "known-good")
            self.assertFalse(self.command(state, "settings")["privacy.telemetry"])
            log = state / "diagnostics" / app_id / "activity.log"
            with log.open("a", encoding="utf-8") as handle:
                handle.write(f"path={state} token=super-secret-value\n")
            bundle = root / "support.zip"
            self.command(state, "support-bundle", str(bundle))
            with zipfile.ZipFile(bundle) as archive:
                combined = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())
            self.assertNotIn(str(state), combined)
            self.assertNotIn("super-secret-value", combined)
            self.assertIn("<redacted>", combined)
            self.assertIn("bundle.json", zipfile.ZipFile(bundle).namelist())
