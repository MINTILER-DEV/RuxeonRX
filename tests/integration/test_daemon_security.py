import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk/bindings/python"))
from rxipc import Client


@unittest.skipIf(os.name == "nt", "AF_UNIX service acceptance runs on Linux")
class DaemonTest(unittest.TestCase):
    def test_package_replacement_retires_process_and_portal_authority(self):
        sys.path.insert(0, str(ROOT / "services/rx-appd"))
        from daemon import DesktopService
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); service = DesktopService(root / "state", root / "run")
            app_id = "org.ruxeonrx.native-test-app"
            packages = []
            for version in ("0.1.0", "0.2.0"):
                manifest = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
                manifest["version"] = version
                package = root / (version + ".rxpkg")
                with zipfile.ZipFile(package, "w") as archive:
                    archive.writestr("manifest.json", json.dumps(manifest))
                    archive.writestr("main.py", "print('regression fixture')")
                packages.append(package)
            service.dispatch("install", {"path": str(packages[0])})
            for method, params in (("update", {"path": str(packages[1])}), ("repair", {"app_id": app_id}), ("rollback", {"app_id": app_id})):
                process = Mock(); process.poll.return_value = None
                service.processes[app_id] = process; service.tokens["obsolete"] = app_id
                service.requests["pending"] = {"app_id": app_id, "pending": True}
                service.dispatch(method, params)
                process.terminate.assert_called_once(); process.wait.assert_called_once_with(timeout=5)
                self.assertNotIn(app_id, service.processes)
                self.assertNotIn("obsolete", service.tokens); self.assertNotIn("pending", service.requests)

    def test_app_appearance_is_token_scoped_and_exposes_only_the_public_color_scheme(self):
        sys.path.insert(0, str(ROOT / "services/rx-appd"))
        from daemon import DesktopService
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); service = DesktopService(root / "state", root / "run")
            app = service.manager.install_manifest(ROOT / "packages/native-test-app/manifest.json")
            process = Mock(); process.poll.return_value = None
            service.tokens["live-token"] = app["id"]; service.processes[app["id"]] = process
            self.assertEqual({"color_scheme": "prefer-dark"}, service.portal("appearance", {"token": "live-token"}))
            service.settings.set("appearance.color_scheme", "prefer-light")
            self.assertEqual({"color_scheme": "prefer-light"}, service.portal("appearance", {"token": "live-token"}))
            with self.assertRaises(PermissionError): service.portal("appearance", {"token": "forged"})
            with self.assertRaises(PermissionError): service.portal("settings", {"token": "live-token"})

    def test_requested_login_mode_does_not_mislabel_the_live_service(self):
        sys.path.insert(0, str(ROOT / "services/rx-appd"))
        from daemon import DesktopService
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); state = root / "state"
            normal = DesktopService(state, root / "run")
            (state / "safe-mode").touch()
            health = normal.dispatch("health", {})
            self.assertEqual("normal", health["mode"])
            self.assertEqual("safe", health["next_login_mode"])
            recovery = DesktopService(state, root / "run")
            (state / "safe-mode").unlink()
            health = recovery.dispatch("health", {})
            self.assertEqual("safe", health["mode"])
            self.assertEqual("normal", health["next_login_mode"])

    def test_file_and_protocol_intents_are_scoped_and_require_file_consent(self):
        sys.path.insert(0, str(ROOT / "services/rx-appd"))
        from daemon import DesktopService
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = DesktopService(root / "state", root / "run")
            app = service.manager.install_manifest(ROOT / "packages/native-test-app/manifest.json")
            document = root / "a document.txt"; document.write_text("private document")
            identifier = service.file_intent(app["id"], document.as_uri())
            self.assertTrue(service.requests[identifier]["pending"])
            self.assertEqual(str(document), service.requests[identifier]["suggested_path"])
            self.assertEqual([], service.manager.portal.file_grants(app["id"]))
            link = service.file_intent(app["id"], "rxsample:hello")
            self.assertEqual("rxsample:hello", service.requests[link]["content"])
            with self.assertRaises(ValueError): service.file_intent(app["id"], "unknown:hello")
            with self.assertRaises(ValueError): service.file_intent(app["id"], "file://remote/file.txt")

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
