import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rx-appd"))
from rx_appd import AppRegistry


class ManifestValidation(unittest.TestCase):
    def test_malformed_inputs_and_traversal_identity_are_rejected(self):
        base = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
        for field, value in (("id", "../../outside"), ("version", "../2"), ("launch", "shell"), ("requested_permissions", ["admin"]), ("handlers", ["not-a-mime"]), ("package_kind", "invented"), ("sandbox", "false"), ("icon", "../escape.svg")):
            with self.subTest(field=field):
                candidate = {**base, field: value}
                with self.assertRaises(ValueError): AppRegistry._validate(candidate)
