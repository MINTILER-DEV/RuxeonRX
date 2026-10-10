import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rx-diagnosticsd"))
from rx_diagnosticsd import Diagnostics


class DiagnosticRedaction(unittest.TestCase):
    def test_json_url_credentials_and_short_usernames(self):
        with patch.dict(os.environ, {"USER": "rx", "USERNAME": "rx"}):
            result = Diagnostics(Path("/home/rx/state"), {}).scrub(
                'org.ruxeonrx.notes {"token": "private-token", "api_key": "private-key"} '
                'https://person:private-password@example.org/catalog?token=private-query')
        for secret in ("private-token", "private-key", "private-password", "private-query"):
            self.assertNotIn(secret, result)
        self.assertIn("org.ruxeonrx.notes", result)
