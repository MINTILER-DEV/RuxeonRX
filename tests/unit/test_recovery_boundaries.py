from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rx-recoveryd"))
from rx_recoveryd import Recovery


class RecoveryBoundaries(unittest.TestCase):
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
