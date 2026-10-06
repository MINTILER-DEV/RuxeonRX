import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RXCTL = ROOT / "tools" / "rxctl"
V1 = ROOT / "packages" / "native-test-app" / "manifest.json"
V2 = ROOT / "packages" / "native-test-app" / "versions" / "0.2.0.json"


class RX03NativeManagementTest(unittest.TestCase):
    def command(self, state: Path, *arguments: str) -> object:
        completed = subprocess.run([sys.executable, str(RXCTL), "--state", str(state), *arguments], check=True, text=True, capture_output=True)
        return json.loads(completed.stdout)

    def test_update_repair_rollback_associations_and_portal_file_grant(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            document = state / "notes.txt"
            document.write_text("private notes", encoding="utf-8")
            app = self.command(state, "install", str(V1))
            app_id = app["id"]
            self.command(state, "add-source", "ruxeon", "https://packages.example.invalid/rx")
            self.assertIn("ruxeon", self.command(state, "sources"))
            self.command(state, "decide", app_id, "files", "allow")
            self.assertEqual(str(document.resolve()), self.command(state, "grant-file", app_id, str(document))["path"])
            self.assertEqual(app_id, self.command(state, "defaults")["text/plain"])
            updated = self.command(state, "update", str(V2))
            self.assertEqual("0.2.0", updated["version"])
            self.assertEqual(["rx-native-test-app", "--stable"], self.command(state, "launch", app_id)["command"])
            repaired = self.command(state, "repair", app_id)
            self.assertEqual("0.2.0", repaired["version"])
            rolled_back = self.command(state, "rollback", app_id)
            self.assertEqual("0.1.0", rolled_back["version"])
            details = self.command(state, "inspect", app_id)
            self.assertEqual([str(document.resolve())], details["file_grants"])
            self.assertGreater(details["storage_bytes"], 0)
            self.command(state, "remove", app_id, "--purge-data")
            self.assertEqual({}, self.command(state, "defaults"))
            self.assertEqual({}, self.command(state, "permissions"))

    def test_invalid_update_preserves_installed_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            app_id = self.command(state, "install", str(V1))["id"]
            invalid = state / "invalid.json"
            invalid.write_text('{"id": "org.ruxeonrx.native-test-app", "version": "bad"}', encoding="utf-8")
            failed = subprocess.run([sys.executable, str(RXCTL), "--state", str(state), "update", str(invalid)], text=True, capture_output=True)
            self.assertNotEqual(0, failed.returncode)
            self.assertEqual("0.1.0", self.command(state, "inspect", app_id)["app"]["version"])
