import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rx-appd"))
from rx_appd import AppRegistry


class ManifestValidation(unittest.TestCase):
    def test_semantically_corrupted_registry_cannot_purge_outside_managed_state(self):
        sys.path.insert(0, str(ROOT / "shell"))
        from app_manager import AppManager
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = AppManager(root / "state")
            victim = root / "victim"; victim.mkdir()
            marker = victim / "keep.txt"; marker.write_text("unrelated user data")
            bad = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
            bad["id"] = "../../victim"
            manager.registry.path.write_text(json.dumps({bad["id"]: bad}))
            with self.assertRaises(ValueError): manager.remove(bad["id"], purge_data=True)
            self.assertEqual("unrelated user data", marker.read_text())

    def test_malformed_inputs_and_traversal_identity_are_rejected(self):
        base = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
        for field, value in (("id", "../../outside"), ("version", "../2"), ("launch", "shell"), ("requested_permissions", ["admin"]), ("handlers", ["not-a-mime"]), ("package_kind", "invented"), ("sandbox", "false"), ("icon", "../escape.svg"), ("name", "app\rExec=bad"), ("source", "test\x00source")):
            with self.subTest(field=field):
                candidate = {**base, field: value}
                with self.assertRaises(ValueError): AppRegistry._validate(candidate)
