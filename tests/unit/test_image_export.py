import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("rx_export", Path(__file__).resolve().parents[2] / "tools/rx-export.py")
export = importlib.util.module_from_spec(spec); spec.loader.exec_module(export)


class ImageExport(unittest.TestCase):
    def fixture(self, root):
        source = root / "source.qcow2"; source.write_bytes(b"frozen image")
        manifest = root / "artifact.json"
        manifest.write_text(json.dumps({"revision": "verified-runtime", "disk_sha256": export.checksum(source)}))
        output = root / "portable.qcow2"
        return source, manifest, output, ["rx-export", str(output), "--disk", str(source), "--manifest", str(manifest)]

    def test_portable_manifest_records_actual_export_and_frozen_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, manifest, output, arguments = self.fixture(Path(temporary))
            def convert(command, **unused): Path(command[-1]).write_bytes(b"compressed standalone image")
            with patch("sys.argv", arguments), patch.object(export.subprocess, "run", side_effect=convert), patch("sys.stdout", new=io.StringIO()): export.main()
            result = json.loads(output.with_suffix(".json").read_text())
            self.assertEqual("verified-runtime", result["revision"])
            self.assertEqual(export.checksum(source), result["source_disk_sha256"])
            self.assertEqual(export.checksum(output), result["disk_sha256"])
            self.assertEqual(b"frozen image", source.read_bytes())

    def test_existing_export_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, manifest, output, arguments = self.fixture(Path(temporary)); output.write_bytes(b"user image")
            with patch("sys.argv", arguments), patch("sys.stderr", new=io.StringIO()), patch.object(export.subprocess, "run") as run, self.assertRaises(SystemExit): export.main()
            run.assert_not_called(); self.assertEqual(b"user image", output.read_bytes())

    def test_changed_source_cannot_be_exported_with_stale_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, manifest, output, arguments = self.fixture(Path(temporary)); source.write_bytes(b"changed image")
            with patch("sys.argv", arguments), patch("sys.stderr", new=io.StringIO()), patch.object(export.subprocess, "run") as run, self.assertRaises(SystemExit): export.main()
            run.assert_not_called(); self.assertFalse(output.exists())

    def test_source_mutation_during_export_keeps_only_incomplete_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, manifest, output, arguments = self.fixture(Path(temporary))
            def convert(command, **unused):
                Path(command[-1]).write_bytes(b"incomplete image"); source.write_bytes(b"concurrent mutation")
            with patch("sys.argv", arguments), patch.object(export.subprocess, "run", side_effect=convert), self.assertRaisesRegex(RuntimeError, "source changed"): export.main()
            self.assertFalse(output.exists()); self.assertFalse(output.with_suffix(".json").exists())
            self.assertTrue(output.with_name(output.name + ".partial").exists())
