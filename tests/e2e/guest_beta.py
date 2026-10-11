"""Actual GNOME taskbar + GTK native beta acceptance, followed by recovery."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path("/opt/RuxeonRX")
sys.path[:0] = [str(ROOT / "sdk/bindings/python"), str(ROOT / "tests/e2e")]
from rxipc import Client
from guest_desktop import wait, window, xdo, sandbox_boundary


def setup():
    runtime = Path(os.environ["RX_RUNTIME"])
    environment = runtime / "environment.json"
    wait(environment.is_file, "real session environment", timeout=180)
    os.environ.update(json.loads(environment.read_text()))
    import pyatspi
    return runtime, Client(runtime / "appd.sock"), pyatspi


def descendants(node, depth=0):
    yield node
    if depth > 18: return
    try:
        for child in node:
            if child: yield from descendants(child, depth + 1)
    except Exception: pass


def control(atspi, name, app=None):
    for application in atspi.Registry.getDesktop(0):
        if app and application.name != app: continue
        for node in descendants(application):
            try:
                if node.name == name and node.getState().contains(atspi.STATE_SHOWING): return node
            except Exception: pass


def click(atspi, name, app=None):
    node = wait(lambda: control(atspi, name, app), "visible accessible control: " + name)
    extents = node.queryComponent().getExtents(atspi.DESKTOP_COORDS)
    assert extents.width > 0 and extents.height > 0
    xdo("mousemove", str(extents.x + extents.width // 2), str(extents.y + extents.height // 2)); xdo("click", "1")


def consent(atspi, allowed):
    wait(lambda: window("RuxeonRX permission"), "actual GTK permission dialog")
    click(atspi, "Allow" if allowed else "Deny")


def open_picker(filename):
    chooser = wait(lambda: window("Open"), "real GTK file picker")
    xdo("windowactivate", "--sync", chooser)
    xdo("key", "--clearmodifiers", "ctrl+l"); xdo("type", "--clearmodifiers", str(filename)); xdo("key", "Return")


def class_window(name):
    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", name], capture_output=True, text=True)
    return result.stdout.strip().splitlines()[0] if result.returncode == 0 else None


def main(phase):
    runtime, client, atspi = setup()
    shell_name = "RX Recovery" if phase == "safe" else "RX Apps"
    wait(lambda: (runtime / "graphical-ready").is_file() and window(shell_name), "real GTK management/recovery window", timeout=180)
    assert client.call("health")["healthy"]
    app_id = "org.ruxeonrx.native-test-app"
    if phase == "safe":
        assert client.call("health")["mode"] == "safe"
        client.call("restore", name="acceptance-good")
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0"
        xdo("windowactivate", "--sync", window(shell_name)); xdo("key", "F5")
    else:
        extension = subprocess.check_output(["gnome-extensions", "info", "dash-to-panel@jderose9.github.com"], text=True)
        assert "ACTIVE" in extension or "ENABLED" in extension, extension
        assert "BOTTOM" in subprocess.check_output(["gsettings", "get", "org.gnome.shell.extensions.dash-to-panel", "panel-position"], text=True)
        assert subprocess.run(["pgrep", "-x", "gnome-shell"], stdout=subprocess.DEVNULL).returncode == 0
        if phase == "initial":
            sandbox_boundary(client)
            assert len([app for app in client.call("apps") if app.get("unrestricted")]) >= 4
            assert client.call("defaults")["inode/directory"] == "org.ruxeonrx.import.org.gnome.nautilus"
            shell = window("RX Apps"); xdo("windowactivate", "--sync", shell); xdo("key", "ctrl+i")
            wait(lambda: client.call("apps", query="RX Notes"), "native package installed through GTK UI")
            xdo("key", "ctrl+f"); xdo("type", "no-such-app"); time.sleep(1); xdo("key", "ctrl+l")
            assert client.call("inspect", app_id=app_id)["app"]["launch_count"] == 0
            xdo("key", "ctrl+f", "ctrl+a"); xdo("type", "RX Notes"); time.sleep(1); xdo("key", "ctrl+l")
            notes = wait(lambda: window("RX Notes"), "native GTK Notes window")
            click(atspi, "Send notification"); consent(atspi, False)
            wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("notifications") is False, "notification denial")
            click(atspi, "Send notification"); consent(atspi, True)
            wait(lambda: client.call("notifications"), "allowed desktop notification")
            click(atspi, "Open file…"); consent(atspi, False)
            wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("files") is False, "file denial")
            document = Path.home() / "beta-portal.txt"; document.write_text("A real document opened with consent in the modern desktop.\n")
            click(atspi, "Open file…"); consent(atspi, True); open_picker(document)
            wait(lambda: str(document) in client.call("inspect", app_id=app_id)["file_grants"], "chosen-file grant")
            click(atspi, "Save locally")
            saved = Path.home() / ".local/state/ruxeonrx/data" / app_id / "note.txt"
            wait(lambda: saved.is_file() and "real document" in saved.read_text(), "native app private saved note")
            # Actual taskbar click switches to Files, not a fabricated appd launch count.
            click(atspi, "Files", app="gnome-shell")
            files = wait(lambda: window("Home") or window("Files"), "Files launched from bottom taskbar")
            xdo("windowactivate", "--sync", files); xdo("key", "alt+F4")
            for suffix, wm_class, intent in (("org.gnome.console", "org.gnome.Console", None), ("org.gnome.texteditor", "org.gnome.TextEditor", str(document)), ("firefox-esr", "firefox", "about:blank")):
                native_id = "org.ruxeonrx.import." + suffix
                client.call("launch", app_id=native_id, **({"path": intent} if intent else {}))
                native_window = wait(lambda name=wm_class: class_window(name), "real trusted native window: " + suffix, timeout=240)
                print("BASE_NATIVE_WINDOW=" + native_id, flush=True)
                xdo("windowactivate", "--sync", native_window); xdo("key", "alt+F4")
            assert client.call("defaults")["https:"] == "org.ruxeonrx.import.firefox-esr"
            xdo("windowactivate", "--sync", shell); click(atspi, "System settings")
            settings_window = wait(lambda: class_window("org.gnome.Settings"), "real native system settings", timeout=180)
            xdo("windowactivate", "--sync", settings_window); xdo("key", "alt+F4")
            xdo("windowactivate", "--sync", shell); xdo("key", "alt+F4")
            wait(lambda: not window("RX Apps"), "management window closed without stopping permission UI")
            subprocess.run(["python3", str(ROOT / "shell/modern.py"), "--page", "apps"], check=True, timeout=30)
            shell = wait(lambda: window("RX Apps"), "management application reopened through its launcher")
            xdo("windowactivate", "--sync", shell); xdo("key", "ctrl+d")
            log = wait(lambda: window("Application diagnostics"), "GTK log viewer"); xdo("windowactivate", "--sync", log); xdo("key", "alt+F4")
            client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))
            client.call("rollback", app_id=app_id)
            assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.1.0"
            client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg")); client.call("repair", app_id=app_id)
            client.call("pin", app_id=app_id, pinned=True)
            assert "ruxeonrx-" + app_id + ".desktop" in subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"], text=True)
            client.call("set", key="appearance.text_scale", value=1.25)
            client.call("set", key="appearance.high_contrast", value=True)
            assert "1.25" in subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"], text=True)
            client.call("snapshot", name="acceptance-good"); client.call("bundle", path=str(Path.home() / "support-beta.zip"))
            xdo("windowactivate", "--sync", shell); xdo("key", "F5"); xdo("windowactivate", "--sync", notes)
        else:
            app = client.call("inspect", app_id=app_id)
            assert app["app"]["version"] == "0.2.0" and app["app"]["pinned"] and app["permissions"]["notifications"]
            assert client.call("settings")["appearance.text_scale"] == 1.25
            client.call("launch", app_id=app_id); wait(lambda: window("RX Notes"), "saved native app after reboot")
            client.call("remove", app_id=app_id, purge_data=True)
            assert not client.call("apps", query="RX Notes")
            assert app_id not in client.call("defaults").values()
            assert "ruxeonrx-" + app_id + ".desktop" not in subprocess.check_output(["gsettings", "get", "org.gnome.shell", "favorite-apps"], text=True)
            client.call("restore", name="acceptance-good")
            session = Path.home() / ".local/state/ruxeonrx/session.json"
            for service in ("rx-appd", "rx-shell"):
                old_pid = json.loads(session.read_text())["pids"][service]; os.kill(old_pid, signal.SIGTERM)
                wait(lambda: json.loads(session.read_text())["pids"][service] != old_pid and client.call("health")["healthy"] and window("RX Apps"), "real " + service + " crash recovery", timeout=180)
            for filename in ("apps.json", "apps.backup", "settings.json", "sources.json"):
                (session.parent / filename).write_text("{simulated interrupted write")
    subprocess.run(["scrot", "--overwrite", str(Path.home() / "desktop-acceptance.png")], check=True)
    print(json.dumps({"phase": phase, "passed": True, "real_graphics": True, "desktop": "GNOME" if phase != "safe" else "minimal-recovery"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("initial", "resume", "safe"), required=True)
    try: main(parser.parse_args().phase)
    except Exception:
        subprocess.run(["scrot", "--overwrite", str(Path.home() / "desktop-acceptance.png")])
        for path in (Path.home() / ".local/state/ruxeonrx").rglob("*.log"):
            if "snapshots" not in path.parts: print(str(path) + "\n" + path.read_text(errors="replace")[-4000:], file=sys.stderr)
        raise
