from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rx-recoveryd"))
from rx_recoveryd import Recovery


class RecoveryBoundaries(unittest.TestCase):
    def test_failed_snapshot_creation_keeps_previous_good_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); recovery = Recovery(state)
            (state / "apps.json").write_text("known good")
            target = recovery.create("good"); before = target.read_bytes()
            with patch.object(zipfile.ZipFile, "write", side_effect=OSError("simulated disk failure")):
                with self.assertRaises(OSError): recovery.create("good")
            self.assertEqual(before, target.read_bytes())

    def test_rejects_whole_archive_before_modifying_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            recovery = Recovery(state)
            marker = state / "apps.json"; marker.write_text("original")
            with zipfile.ZipFile(recovery.snapshot_dir / "bad.zip", "w") as archive:
                archive.writestr("apps.json", "modified")
                archive.writestr("../escape.txt", "escape")
            with self.assertRaises(ValueError): recovery.restore("bad")
            self.assertEqual("original", marker.read_text())

    def test_restore_removes_post_snapshot_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); recovery = Recovery(state)
            (state / "apps.json").write_text("before")
            recovery.create("good")
            (state / "after.json").write_text("after")
            (state / "apps.json").write_text("changed")
            recovery.restore("good")
            self.assertEqual("before", (state / "apps.json").read_text())
            self.assertFalse((state / "after.json").exists())

    def test_restore_preserves_live_process_metadata_and_log_handles(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary); recovery = Recovery(state)
            session = state / "session.json"; session.write_text("old pid")
            logs = state / "session-logs"; logs.mkdir()
            log = logs / "shell.log"; log.write_text("before\n")
            recovery.create("good")
            session.write_text("current pid")
            with log.open("a") as handle:
                recovery.restore("good")
                handle.write("after\n"); handle.flush()
                self.assertEqual("before\nafter\n", log.read_text())
            self.assertEqual("current pid", session.read_text())
