import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "shell"), str(ROOT / "services/rx-settingsd")]
from system_integration import apply_settings, sync_favorites
from rx_settingsd import Settings
from app_manager import AppManager


class DesktopIntegration(unittest.TestCase):
    def test_preferences_apply_to_real_gnome_schemas_only_in_rx_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings(Path(temporary))
            values = settings.set("appearance.color_scheme", "prefer-light")
            with self.assertRaises(ValueError): settings.set("appearance.color_scheme", "invented")
            with patch("system_integration.active", return_value=False), patch("system_integration.subprocess.run") as run:
                apply_settings(values); run.assert_not_called()
            with patch("system_integration.active", return_value=True), patch("system_integration.subprocess.run") as run:
                run.return_value.returncode = 0
                apply_settings(values)
                commands = [call.args[0] for call in run.call_args_list]
                self.assertIn(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "'prefer-light'"], commands)
                self.assertIn(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", "1.0"], commands)

    def test_favorites_preserve_user_entries_and_remove_unpinned_managed_apps(self):
        with patch("system_integration.active", return_value=True), patch("system_integration.subprocess.check_output", return_value="['other.desktop','ruxeonrx-org.test.old.desktop']"), patch("system_integration.subprocess.run") as run:
            sync_favorites([{"id": "org.test.new", "pinned": True}])
            argument = run.call_args.args[0][-1]
            self.assertIn("other.desktop", argument)
            self.assertIn("ruxeonrx-org.test.new.desktop", argument)
            self.assertNotIn("org.test.old", argument)

    def test_native_launch_intent_is_argument_not_shell_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manager = AppManager(root / "state")
            path = root / "sample.desktop"
            path.write_text('[Desktop Entry]\nType=Application\nName=Sample\nExec=python3 -c "import sys; print(sys.argv[1])" %u\n')
            app = manager.import_desktop(path)
            process = manager.execute(app["id"], intent="file:///tmp/hello;not-a-shell-command.txt")
            self.assertEqual(0, process.wait(timeout=10))
            self.assertIn("file:///tmp/hello;not-a-shell-command.txt", "\n".join(manager.logs(app["id"])))
