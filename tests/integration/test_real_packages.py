import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shell"))
from app_manager import AppManager


class RealPackageTest(unittest.TestCase):
    def package(self, directory, version="1", payload="print('native executable ran')"):
        manifest = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
        manifest.update(version=version, launch={"command": [sys.executable, "{package}/main.py"]})
        path = directory / (version + ".rxpkg")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("main.py", payload)
        return path

    def test_payload_runs_tamper_blocks_launch_and_repair_restores_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = AppManager(root / "state")
            package = self.package(root)
            app = manager.install_manifest(package)
            process = manager.execute(app["id"])
            self.assertEqual(0, process.wait(timeout=10))
            output = manager.log_root / app["id"] / "process.log"
            self.assertIn("native executable ran", output.read_text())
            executable = Path(app["package"]["root"]) / "main.py"
            executable.write_text("raise SystemExit(9)")
            with self.assertRaises(ValueError): manager.execute(app["id"])
            manager.repair(app["id"])
            self.assertIn("native executable ran", executable.read_text())
            self.assertEqual(0, manager.execute(app["id"]).wait(timeout=10))
            manager.update(self.package(root, "2", "print('version two')"))
            self.assertEqual("2", manager.inspect(app["id"])["app"]["version"])
            manager.rollback(app["id"])
            self.assertEqual("1", manager.inspect(app["id"])["app"]["version"])

    def test_traversal_and_invalid_version_fail_without_registry_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manager = AppManager(root / "state")
            malicious = root / "evil.rxpkg"
            with zipfile.ZipFile(malicious, "w") as archive: archive.writestr("../outside.txt", "escape")
            with self.assertRaises(ValueError): manager.install_manifest(malicious)
            self.assertEqual([], manager.registry.list())
            self.assertFalse((root / "outside.txt").exists())

    def test_source_download_enforces_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manager = AppManager(root / "state")
            package = self.package(root)
            app_id = "org.ruxeonrx.native-test-app"
            index = root / "index.json"
            catalog = {"format": 1, "packages": [{"id": app_id, "url": package.as_uri(), "sha256": "0" * 64}]}
            index.write_text(json.dumps(catalog))
            manager.packages.add_source("test", index.as_uri())
            with self.assertRaises(ValueError): manager.packages.from_source("test", app_id)
            self.assertEqual([], manager.registry.list())
            catalog["packages"][0]["sha256"] = hashlib.sha256(package.read_bytes()).hexdigest()
            index.write_text(json.dumps(catalog))
            self.assertEqual(app_id, manager.packages.from_source("test", app_id)["id"])

    def test_failed_executable_update_keeps_previous_payload_and_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manager = AppManager(root / "state")
            app = manager.install_manifest(self.package(root))
            manager.decide(app["id"], "notifications", True)
            invalid = self.package(root, "2", "def broken(:")
            with self.assertRaises(ValueError): manager.update(invalid)
            details = manager.inspect(app["id"])
            self.assertEqual("1", details["app"]["version"])
            self.assertTrue(details["permissions"]["notifications"])
            self.assertEqual(0, manager.execute(app["id"]).wait(timeout=10))
