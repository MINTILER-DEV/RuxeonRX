import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk/bindings/python"))
from rxipc import Client


@unittest.skipIf(os.name == "nt", "AF_UNIX service acceptance runs on Linux")
class DaemonTest(unittest.TestCase):
    def test_single_writer_and_restricted_portal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "run"
            daemon = subprocess.Popen([sys.executable, str(ROOT / "services/rx-appd/daemon.py"), "--state", str(root / "state"), "--runtime", str(runtime)], stdout=subprocess.DEVNULL, env={**os.environ, "HOME": str(root / "home")})
            try:
                limit = time.monotonic() + 10
                while not (runtime / "appd.sock").exists() and time.monotonic() < limit: time.sleep(0.05)
                admin = Client(runtime / "appd.sock")
                portal = Client(runtime / "portal/portal.sock")
                self.assertTrue(admin.call("health")["healthy"])
                app = admin.call("install", path=str(ROOT / "packages/native-test-app/manifest.json"))
                with self.assertRaises(RuntimeError): portal.call("decide", app_id=app["id"], capability="files", allowed=True)
                with self.assertRaises(RuntimeError): portal.call("request", token="forged", capability="files")
                self.assertEqual({}, admin.call("inspect", app_id=app["id"])["permissions"])
                self.assertTrue((root / "home/.local/share/applications" / ("ruxeonrx-" + app["id"] + ".desktop")).exists())
                admin.call("remove", app_id=app["id"], purge_data=True)
                self.assertFalse((root / "home/.local/share/applications" / ("ruxeonrx-" + app["id"] + ".desktop")).exists())
            finally:
                daemon.terminate(); daemon.wait(timeout=5)
