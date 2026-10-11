"""Actual GNOME taskbar + GTK native beta acceptance, followed by recovery."""
import argparse
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path("/opt/RuxeonRX")
sys.path[:0] = [str(ROOT / "sdk/bindings/python"), str(ROOT / "tests/e2e")]
from rxipc import Client
from guest_desktop import wait, window, xdo, sandbox_boundary, managed_window


def setup():
    runtime = Path(os.environ["RX_RUNTIME"])
    environment = runtime / "environment.json"
    wait(environment.is_file, "real session environment", timeout=420)
    os.environ.update(json.loads(environment.read_text()))
    return runtime, Client(runtime / "appd.sock")


def descendants(node, depth=0):
    yield node
    # Adwaita preference groups nest real buttons beyond eighteen levels.
    if depth > 40: return
    try:
        for child in node:
            if child: yield from descendants(child, depth + 1)
    except Exception: pass


def control(atspi, name, app=None, prefix=False):
    if app is None:
        app = "org.ruxeonrx.native-test-app" if name in ("Send notification", "Open file…", "Save locally") or name.startswith("Opened ") else "modern.py"
    for application in reversed(list(atspi.Registry.getDesktop(0))):
        try:
            if app and app != "*" and application.name != app: continue
        except Exception: continue
        roots = [child for child in application if child and child.name == "Open"] if app == "*" else [application]
        for node in (node for root in roots for node in descendants(root)):
            try:
                if (node.name == name or prefix and node.name.startswith(name)) and node.getState().contains(atspi.STATE_SHOWING): return node
            except Exception: pass


def click(atspi, name, app=None):
    node = wait(lambda: control(atspi, name, app), "visible accessible control: " + name)
    if app != "gnome-shell":
        # Activate the real GTK accessible widget, not an IPC replacement for
        # its behavior. CSD/transient animations can invalidate X11 coordinates
        # between activation and a pointer click on slow software renderers.
        if node.getRoleName() in ("push button", "button"):
            action = node.queryAction()
            assert action.nActions > 0 and action.doAction(0)
            print("REAL_GTK_ACTION=" + name, flush=True)
            return
        if node.getRoleName() in ("text", "entry"):
            try: focused = node.queryComponent().grabFocus()
            except Exception: focused = False
            if focused:
                print("REAL_GTK_FOCUS=" + name, flush=True)
                return
    if app == "gnome-shell":
        extents = node.queryComponent().getExtents(atspi.DESKTOP_COORDS)
        origin_x = origin_y = 0
    else:
        # GTK 4.18 explicitly returns (0, 0) for unsupported SCREEN
        # coordinates. Its WINDOW coordinates plus the real X11 origin are
        # usable; raise that actual window before clicking an obscured control.
        parent = node; target = None
        while parent:
            if parent.name: target = window(parent.name)
            if target: break
            parent = parent.parent
        if not target: target = xdo("getactivewindow")
        xdo("windowactivate", "--sync", target)
        extents = node.queryComponent().getExtents(atspi.WINDOW_COORDS)
        geometry = subprocess.check_output(["xwininfo", "-id", target], text=True)
        origin_x = int(re.search(r"Absolute upper-left X:\s*(-?\d+)", geometry).group(1))
        origin_y = int(re.search(r"Absolute upper-left Y:\s*(-?\d+)", geometry).group(1))
    assert extents.width > 0 and extents.height > 0
    x = origin_x + extents.x + extents.width // 2; y = origin_y + extents.y + extents.height // 2
    print(f"REAL_UI_CLICK={name}@{x},{y}", flush=True)
    xdo("mousemove", str(x), str(y)); xdo("click", "1")


def consent(atspi, allowed):
    wait(lambda: window("RuxeonRX permission"), "actual GTK permission dialog")
    click(atspi, "Allow" if allowed else "Deny")


def open_picker(filename, atspi):
    chooser = wait(lambda: window("Open"), "real GTK file picker")
    # Use GTK's actual _Open mnemonic once selection is ready, not a second
    # Enter (which can cancel while location processing is pending). The next
    # assertions verify the exact granted path and delivered file contents.
    def accept():
        current = window("Open")
        if not current: return True
        xdo("windowactivate", "--sync", current)
        # GNOME's Nautilus chooser keeps search above its location bar; Ctrl+L
        # alone cannot escape a raced type-to-search operation. Toggle the
        # actual search control off if active, also supporting GTK's fallback.
        search = control(atspi, "Search Current Folder", app="*") or control(atspi, "Search", app="*")
        if search and search.getRoleName() == "toggle button" and any(search.getState().contains(state) for state in (atspi.STATE_PRESSED, atspi.STATE_CHECKED)):
            assert search.queryAction().doAction(0)
            print("REAL_GTK_ACTION=Exit chooser search", flush=True)
            time.sleep(1)
        # A mapped native chooser can still be initializing its shortcuts.
        # Retry real location navigation rather than leaving a raced path in
        # the chooser's type-to-search field until the acceptance times out.
        xdo("key", "--clearmodifiers", "ctrl+l")
        time.sleep(1)
        xdo("key", "--clearmodifiers", "ctrl+a")
        xdo("type", "--clearmodifiers", str(filename)); xdo("key", "Return")
        time.sleep(2)
        xdo("key", "--clearmodifiers", "alt+o")
        return not window("Open")
    wait(accept, "actual file chooser Open response")


def class_window(name):
    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", name], capture_output=True, text=True)
    target = managed_window(result.stdout) if result.returncode == 0 else None
    if target: return target
    # GNOME Console's real X11 class is kgx, not org.gnome.Console.
    # GTK exports the actual app ID independently of the executable class.
    clients = subprocess.check_output(["xprop", "-root", "_NET_CLIENT_LIST"], text=True, timeout=5)
    for identifier in re.findall(r"0x[0-9a-fA-F]+", clients):
        identity = subprocess.check_output(["xprop", "-id", identifier, "_GTK_APPLICATION_ID"], text=True, timeout=5)
        if '"' + name + '"' in identity and managed_window(identifier): return identifier
    return None


def main(phase):
    runtime, client = setup()
    shell_name = "RX Recovery" if phase == "safe" else "RX Apps"
    wait(lambda: (runtime / "graphical-ready").is_file() and window(shell_name), "real GTK management/recovery window", timeout=420)
    assert client.call("health")["healthy"]
    app_id = "org.ruxeonrx.native-test-app"
    if phase == "safe":
        import pyatspi as atspi
        from gi.repository import Atspi
        Atspi.set_timeout(1500, 3000)
        assert client.call("health")["mode"] == "safe"
        click(atspi, "Snapshot name"); xdo("key", "ctrl+a"); xdo("type", "acceptance-good")
        # GTK 4.18's entry Text interface can retain an empty cached value.
        # Restoring the specifically named snapshot below proves the real
        # widget received the keystrokes without substituting a backend call.
        click(atspi, "Restore"); click(atspi, "Continue")
        wait(lambda: client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0", "real GTK corrupt-state snapshot restore")
        assert client.call("health")["mode"] == "safe", "restoring next-login preferences must not mislabel the current recovery session"
        xdo("windowactivate", "--sync", window(shell_name)); xdo("key", "F5")
    else:
        def extension_active():
            extension = subprocess.check_output(["gnome-extensions", "info", "dash-to-panel@jderose9.github.com"], text=True)
            return any(line.strip() in ("State: ACTIVE", "State: ENABLED") for line in extension.splitlines())
        wait(extension_active, "active GNOME taskbar extension", timeout=420)
        import pyatspi as atspi
        from gi.repository import Atspi
        Atspi.set_timeout(1500, 3000)
        assert "BOTTOM" in subprocess.check_output(["gsettings", "get", "org.gnome.shell.extensions.dash-to-panel", "panel-position"], text=True)
        assert subprocess.run(["pgrep", "-x", "gnome-shell"], stdout=subprocess.DEVNULL).returncode == 0
        if phase == "initial":
            assert subprocess.check_output(["gsettings", "get", "org.gnome.desktop.lockdown", "disable-lock-screen"], text=True).strip() == "true", "the passwordless developer profile must not offer manual locking"
            # Check functioning desktop services, not just emulated device names.
            wait(lambda: subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0, "working PipeWire default output")
            network = subprocess.check_output(["nmcli", "-t", "device", "status"], text=True)
            assert ":ethernet:connected:" in network, "NetworkManager must own the working guest network"
            subprocess.run(["scrot", "--overwrite", str(Path.home() / "desktop-default.png")], check=True)
            sandbox_boundary(client)
            assert len([app for app in client.call("apps") if app.get("unrestricted")]) >= 4
            assert client.call("defaults")["inode/directory"] == "org.ruxeonrx.import.org.gnome.nautilus"
            shell = window("RX Apps"); xdo("windowactivate", "--sync", shell); xdo("key", "ctrl+i")
            wait(lambda: client.call("apps", query="RX Notes"), "native package installed through GTK UI")
            xdo("key", "ctrl+f"); xdo("type", "no-such-app")
            wait(lambda: control(atspi, "No matching applications"), "GTK empty search result")
            xdo("key", "ctrl+l")
            assert client.call("inspect", app_id=app_id)["app"]["launch_count"] == 0
            xdo("key", "ctrl+f", "ctrl+a"); xdo("type", "RX Notes")
            wait(lambda: control(atspi, app_id, prefix=True), "filtered GTK selection details")
            xdo("key", "ctrl+l")
            notes = wait(lambda: window("RX Notes"), "native GTK Notes window")
            click(atspi, "Send notification"); consent(atspi, False)
            wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("notifications") is False, "notification denial")
            click(atspi, "Send notification"); consent(atspi, True)
            wait(lambda: client.call("notifications"), "allowed desktop notification")
            click(atspi, "Open file…"); consent(atspi, False)
            wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("files") is False, "file denial")
            document = Path.home() / "beta-portal.txt"; document.write_text("A real document opened with consent in the modern desktop.\n")
            click(atspi, "Open file…"); consent(atspi, True); open_picker(document, atspi)
            wait(lambda: str(document) in client.call("inspect", app_id=app_id)["file_grants"], "chosen-file grant")
            wait(lambda: control(atspi, "Opened beta-portal.txt"), "file content delivered to the real native app")
            click(atspi, "Save locally")
            saved = Path.home() / ".local/state/ruxeonrx/data" / app_id / "note.txt"
            wait(lambda: saved.is_file() and "real document" in saved.read_text(), "native app private saved note")
            xdo("windowactivate", "--sync", notes); xdo("windowminimize", notes)
            wait(lambda: not window("RX Notes"), "managed native window minimized")
            click(atspi, "RX Notes", app="gnome-shell")
            notes = wait(lambda: window("RX Notes"), "managed native window restored through its real taskbar item")
            # Actual taskbar click switches to Files, not a fabricated appd launch count.
            taskbar_files = wait(lambda: control(atspi, "Files", app="gnome-shell"), "visible taskbar Files button")
            bounds = taskbar_files.queryComponent().getExtents(atspi.DESKTOP_COORDS)
            screen_height = int(re.search(r"Height:\s*(\d+)", subprocess.check_output(["xwininfo", "-root"], text=True)).group(1))
            assert bounds.y + bounds.height // 2 > screen_height * 0.8, "taskbar must actually be at the bottom"
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
            xdo("windowactivate", "--sync", shell); xdo("windowminimize", shell)
            wait(lambda: not window("RX Apps"), "real management window minimized")
            click(atspi, "RX Apps", app="gnome-shell")
            shell = wait(lambda: window("RX Apps"), "taskbar restores the minimized window")
            xdo("windowactivate", "--sync", shell); xdo("key", "alt+F4")
            wait(lambda: not window("RX Apps"), "management window closed without stopping permission UI")
            xdo("windowactivate", "--sync", notes)
            click(atspi, "Send notification"); consent(atspi, True)
            wait(lambda: len(client.call("notifications")) >= 2, "permission broker remains usable while the management window is hidden")
            # A modal permission prompt may present its management parent.
            # Close that real window again before exercising taskbar reopening.
            if window("RX Apps"):
                xdo("windowactivate", "--sync", window("RX Apps")); xdo("key", "alt+F4")
                wait(lambda: not window("RX Apps"), "permission parent closed before launcher reactivation")
            click(atspi, "RX Apps", app="gnome-shell")
            shell = wait(lambda: window("RX Apps"), "management application reopened through its taskbar launcher")
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
            # Update/rollback/repair stop the old process by design. Exercise
            # the repaired executable instead of activating its destroyed XID.
            wait(lambda: not window("RX Notes"), "old native executable stopped after package replacement")
            client.call("launch", app_id=app_id)
            notes = wait(lambda: window("RX Notes"), "repaired native app relaunched")
            xdo("windowactivate", "--sync", shell); xdo("key", "F5"); xdo("windowactivate", "--sync", notes)
        else:
            app = client.call("inspect", app_id=app_id)
            assert app["app"]["version"] == "0.2.0" and app["app"]["pinned"] and app["permissions"]["notifications"]
            assert client.call("settings")["appearance.text_scale"] == 1.25
            saved = Path.home() / ".local/state/ruxeonrx/data" / app_id / "note.txt"
            assert "real document" in saved.read_text(), "private note must persist across a real reboot"
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
    subprocess.run(["scrot", "--delay", "2", "--overwrite", str(Path.home() / "desktop-acceptance.png")], check=True)
    print(json.dumps({"phase": phase, "passed": True, "real_graphics": True, "desktop": "GNOME" if phase != "safe" else "minimal-recovery"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("initial", "resume", "safe"), required=True)
    try: main(parser.parse_args().phase)
    except Exception:
        subprocess.run(["scrot", "--overwrite", str(Path.home() / "desktop-acceptance.png")])
        for path in (Path.home() / ".local/state/ruxeonrx").rglob("*.log"):
            if "snapshots" not in path.parts: print(str(path) + "\n" + path.read_text(errors="replace")[-4000:], file=sys.stderr)
        raise
