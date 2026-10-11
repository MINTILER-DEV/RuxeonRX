import json
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "shell"), str(ROOT / "services/rx-settingsd"), str(ROOT / "sdk/bindings/python")]
from system_integration import apply_settings, sync_favorites, reconcile_favorites, reconcile_settings
from rx_settingsd import Settings
from app_manager import AppManager
from rx_notificationd import NotificationCenter
from rxipc import Client


class DesktopIntegration(unittest.TestCase):
    def test_reserved_future_runtime_metadata_cannot_be_launched_as_native(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = AppManager(Path(temporary))
            manifest = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
            manifest["runtime_kind"] = "windows"
            manager.registry.register(manifest)
            with self.assertRaisesRegex(RuntimeError, "native-linux"): manager.execute(manifest["id"])
            self.assertEqual(0, manager.registry.get(manifest["id"])["launch_count"])

    def test_unicode_file_responses_fit_the_bounded_client_reply(self):
        document = "😀" * (1024 * 1024 // 4)
        encoded = (json.dumps({"ok": True, "result": {"content": document}}) + "\n").encode()
        self.assertGreater(len(encoded), 2 * 1024 * 1024)
        with patch("rxipc.socket.AF_UNIX", 1, create=True), patch("rxipc.socket.socket") as factory:
            connection = factory.return_value.__enter__.return_value
            connection.makefile.return_value.__enter__.return_value = io.BytesIO(encoded)
            self.assertEqual(document, Client("test.sock").call("result")["content"])
        with patch("rxipc.socket.AF_UNIX", 1, create=True), patch("rxipc.socket.socket") as factory:
            factory.return_value.__enter__.return_value.makefile.return_value.__enter__.return_value = io.BytesIO(b'{}')
            with self.assertRaises(RuntimeError): Client("test.sock").call("result")

    def test_repeated_notifications_have_distinct_events_and_denial_posts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            center = NotificationCenter(Path(temporary))
            self.assertFalse(center.post("org.test.app", "Same title", "Same body", False))
            self.assertEqual([], center.list())
            self.assertTrue(center.post("org.test.app", "Same title", "Same body", True))
            self.assertTrue(center.post("org.test.app", "Same title", "Same body", True))
            entries = center.list()
            self.assertEqual(2, len(entries))
            self.assertNotEqual(entries[0]["id"], entries[1]["id"])

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

    def test_native_system_settings_changes_are_imported(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings(Path(temporary))
            with patch("system_integration.active", return_value=True), patch("system_integration.subprocess.check_output", side_effect=["1.5", "true", "'prefer-light'", "false", "'sloppy'"]):
                values = reconcile_settings(settings)
            self.assertEqual(1.5, values["appearance.text_scale"])
            self.assertTrue(values["appearance.high_contrast"])
            self.assertEqual("prefer-light", values["appearance.color_scheme"])
            self.assertFalse(values["input.touchpad_natural_scroll"])
            self.assertTrue(values["input.focus_follows_mouse"])

    def test_favorites_preserve_user_entries_and_remove_unpinned_managed_apps(self):
        with patch("system_integration.active", return_value=True), patch("system_integration.subprocess.check_output", return_value="['other.desktop','ruxeonrx-org.test.old.desktop']"), patch("system_integration.subprocess.run") as run:
            sync_favorites([{"id": "org.test.new", "pinned": True}])
            argument = run.call_args.args[0][-1]
            self.assertIn("other.desktop", argument)
            self.assertIn("ruxeonrx-org.test.new.desktop", argument)
            self.assertNotIn("org.test.old", argument)

    def test_native_pins_use_the_original_identity_without_duplicate_wrappers(self):
        with patch("system_integration.active", return_value=True), patch("system_integration.read_favorites", return_value=["org.gnome.Nautilus.desktop", "other.desktop"]), patch("system_integration.subprocess.run") as run:
            sync_favorites([{"id": "org.test.files", "desktop_id": "org.gnome.Nautilus.desktop", "pinned": True}])
            self.assertNotIn("ruxeonrx-org.test.files", run.call_args.args[0][-1])
            sync_favorites([{"id": "org.test.files", "desktop_id": "org.gnome.Nautilus.desktop", "pinned": False}])
            self.assertEqual("['other.desktop']", run.call_args.args[0][-1])

    def test_taskbar_pin_changes_are_imported_without_repinning_core_apps(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = AppManager(Path(temporary) / "state")
            desktop = Path(temporary) / "sample.desktop"
            desktop.write_text('[Desktop Entry]\nType=Application\nName=Test\nExec=true\n')
            app = manager.import_desktop(desktop)
            with patch("system_integration.active", return_value=True), patch("system_integration.read_favorites", return_value=["ruxeonrx-" + app["id"] + ".desktop"]):
                reconcile_favorites(manager)
                self.assertTrue(manager.registry.get(app["id"])["pinned"])
            with patch("system_integration.active", return_value=True), patch("system_integration.read_favorites", return_value=[]), patch("system_integration.subprocess.run") as run:
                reconcile_favorites(manager)
                self.assertFalse(manager.registry.get(app["id"])["pinned"])
                sync_favorites(manager.registry.list())
                self.assertEqual("[]", run.call_args.args[0][-1])

    def test_native_launch_intent_is_argument_not_shell_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manager = AppManager(root / "state")
            path = root / "sample.desktop"
            path.write_text('[Desktop Entry]\nType=Application\nName=Sample\nExec=python3 -c "import sys; print(sys.argv[1])" %u\nMimeType=text/plain;x-scheme-handler/https;\n')
            app = manager.import_desktop(path)
            self.assertEqual(["text/plain", "https:"], app["handlers"])
            process = manager.execute(app["id"], intent="file:///tmp/hello;not-a-shell-command.txt")
            self.assertEqual(0, process.wait(timeout=10))
            self.assertIn("file:///tmp/hello;not-a-shell-command.txt", "\n".join(manager.logs(app["id"])))
