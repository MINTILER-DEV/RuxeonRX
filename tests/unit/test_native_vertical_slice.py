import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "rx-appd"))
sys.path.insert(0, str(ROOT / "services" / "rx-portald"))
sys.path.insert(0, str(ROOT / "sdk" / "samples"))
sys.path.insert(0, str(ROOT / "shell"))

from rx_appd import AppRegistry
from rx_portald import Portal
from native_test_app import run
from launcher import search


class NativeVerticalSliceTest(unittest.TestCase):
    def test_register_search_permission_log_and_uninstall(self):
        manifest = json.loads((ROOT / "packages" / "native-test-app" / "manifest.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            registry = AppRegistry(state)
            registry.register(manifest)

            self.assertEqual([manifest["id"]], [record["id"] for record in search(state, "native")])
            self.assertEqual("file access denied", run(state, manifest["id"]))

            portal = Portal(state)
            portal.decide(manifest["id"], "files", True)
            portal.decide(manifest["id"], "notifications", True)
            self.assertEqual("launched", run(state, manifest["id"]))
            self.assertTrue((state / "diagnostics" / manifest["id"] / "launch.log").exists())

            self.assertTrue(registry.uninstall(manifest["id"]))
            self.assertEqual([], search(state, "native"))
            self.assertIsNone(registry.get(manifest["id"]))


if __name__ == "__main__":
    unittest.main()
