"""Acceptance inside a real graphical QEMU guest; no fabricated ready signals."""
import argparse
import json
import os
import re
import signal
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path("/opt/RuxeonRX")
sys.path.insert(0, str(ROOT / "sdk/bindings/python"))
from rxipc import Client


def wait(predicate, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value: return value
        except Exception: pass
        time.sleep(0.5)
    raise AssertionError("timed out: " + description)


def xdo(*args):
    return subprocess.check_output(["xdotool", *args], text=True, timeout=15).strip()


def window(name):
    answer = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^" + name + "$"], capture_output=True, text=True)
    return answer.stdout.strip().splitlines()[0] if answer.returncode == 0 else None


def click_app(window_id, offset):
    xdo("windowactivate", "--sync", window_id)
    # xdotool's geometry includes reparenting offsets twice under Openbox.
    # Use X11's absolute client origin, not the window-manager frame origin.
    geometry = subprocess.check_output(["xwininfo", "-id", window_id], text=True, timeout=15)
    origin_x = int(re.search(r"Absolute upper-left X:\s*(-?\d+)", geometry).group(1))
    origin_y = int(re.search(r"Absolute upper-left Y:\s*(-?\d+)", geometry).group(1))
    xdo("mousemove", str(origin_x + offset), str(origin_y + 30))
    xdo("click", "1")


def permission(allowed):
    prompt = wait(lambda: window("RuxeonRX permission"), "user-visible portal permission prompt")
    xdo("windowactivate", "--sync", prompt)
    xdo("key", "--clearmodifiers", "alt+y" if allowed else "alt+n")


def main(phase):
    runtime = Path(os.environ["RX_RUNTIME"])
    client = Client(runtime / "appd.sock")
    wait(lambda: (runtime / "graphical-ready").exists() and window("RuxeonRX Desktop"), "real Tk shell window")
    assert client.call("health")["healthy"]
    app_id = "org.ruxeonrx.native-test-app"
    if phase == "safe":
        assert client.call("health")["mode"] == "safe"
        assert (Path.home() / ".local/state/ruxeonrx/safe-mode").is_file()
        client.call("restore", name="acceptance-good")
        assert client.call("health")["healthy"]
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0"
    elif phase == "resume":
        apps = client.call("apps")
        app = next(item for item in apps if item["id"] == app_id)
        assert app["version"] == "0.2.0", "version did not persist across reboot"
        assert app.get("pinned"), "launcher pin did not persist across reboot"
        assert client.call("inspect", app_id=app_id)["permissions"]["notifications"] is True
        assert client.call("settings")["appearance.text_scale"] == 1.25
        assert client.call("settings")["appearance.high_contrast"] is True
        client.call("launch", app_id=app_id)
        wait(lambda: window("RX Notes"), "native app relaunch after reboot")
        client.call("remove", app_id=app_id, purge_data=True)
        assert not client.call("apps", query="RX Notes")
        assert app_id not in client.call("defaults").values()
        client.call("restore", name="acceptance-good")
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0"
        session = Path.home() / ".local/state/ruxeonrx/session.json"
        old_pid = json.loads(session.read_text())["pids"]["rx-appd"]
        os.kill(old_pid, signal.SIGTERM)
        wait(lambda: client.call("health")["pid"] != old_pid and client.call("health")["healthy"], "real daemon crash recovery")
        shell = window("RuxeonRX Desktop")
        old_pid = json.loads(session.read_text())["pids"]["rx-shell"]
        os.kill(old_pid, signal.SIGTERM)
        wait(lambda: json.loads(session.read_text())["pids"]["rx-shell"] != old_pid and window("RuxeonRX Desktop") and client.call("health")["healthy"], "real graphical shell crash recovery")
        # Safe boot must expose recovery even when user-managed JSON is corrupt.
        state = Path.home() / ".local/state/ruxeonrx"
        for filename in ("apps.json", "apps.backup", "settings.json", "sources.json"):
            (state / filename).write_text("{simulated interrupted write")
    else:
        shell = window("RuxeonRX Desktop")
        xdo("windowactivate", "--sync", shell)
        xdo("key", "--clearmodifiers", "ctrl+i")
        wait(lambda: client.call("apps", query="RX Notes"), "install from actual shell keyboard shortcut")
        xdo("key", "--clearmodifiers", "ctrl+f"); xdo("type", "--delay", "40", "no-such-app")
        xdo("key", "--clearmodifiers", "ctrl+l")
        time.sleep(1)
        assert client.call("inspect", app_id=app_id)["app"]["launch_count"] == 0, "empty launcher search still launched an app"
        xdo("key", "--clearmodifiers", "ctrl+f", "ctrl+a"); xdo("type", "--delay", "40", "RX Notes")
        xdo("key", "--clearmodifiers", "ctrl+l")
        notes = wait(lambda: window("RX Notes"), "real native Notes process and window")
        # Trigger notification by clicking the real application control.
        click_app(notes, 175)
        permission(False)
        wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("notifications") is False, "denied notification")
        click_app(notes, 175)
        permission(True)
        wait(lambda: client.call("notifications"), "notification delivery after permission")
        click_app(notes, 65)
        permission(False)
        wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("files") is False, "file access denial")
        document = Path.home() / "portal-acceptance.txt"
        document.write_text("A document outside the sandbox, opened only with consent.\n")
        click_app(notes, 65)
        permission(True)
        chooser = wait(lambda: window("Open"), "controlled native file picker")
        xdo("windowactivate", "--sync", chooser)
        xdo("key", "alt+n"); xdo("type", "--clearmodifiers", str(document)); xdo("key", "Return")
        wait(lambda: str(document) in client.call("inspect", app_id=app_id)["file_grants"], "specific file grant through picker")
        client.call("open-with", handler="text/plain", path=str(document))
        permission(True)
        chooser = wait(lambda: window("Open"), "associated-file portal picker")
        xdo("windowactivate", "--sync", chooser); xdo("key", "Return")
        wait(lambda: not client.call("pending"), "file-open intent handled by the running native app")
        xdo("windowactivate", "--sync", shell); xdo("key", "--clearmodifiers", "ctrl+d")
        log_window = wait(lambda: window("Application diagnostics"), "actual graphical app log viewer")
        xdo("windowactivate", "--sync", log_window); xdo("key", "alt+F4")
        # The same portal contract also works for a regular, unsandboxed native app.
        regular_id = "org.ruxeonrx.regular-notes"
        client.call("install", path=str(ROOT / "packages/catalog/rx-notes-native-0.1.0.rxpkg"))
        client.call("launch", app_id=regular_id)
        regular = wait(lambda: window("RX Notes Native"), "regular native application window")
        click_app(regular, 175)
        permission(True)
        wait(lambda: any(item["app_id"] == regular_id for item in client.call("notifications")), "regular native portal notification")
        client.call("remove", app_id=regular_id, purge_data=True)
        client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0"
        client.call("rollback", app_id=app_id)
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.1.0"
        client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))
        client.call("repair", app_id=app_id)
        client.call("pin", app_id=app_id, pinned=True)
        client.call("set", key="appearance.text_scale", value=1.25)
        client.call("set", key="appearance.high_contrast", value=True)
        client.call("snapshot", name="acceptance-good")
        client.call("bundle", path="/home/rx/support-acceptance.zip")
        xdo("windowactivate", "--sync", shell); xdo("key", "F5")
        xdo("windowactivate", "--sync", notes)
        time.sleep(0.5)
    subprocess.run(["scrot", "--overwrite", "/home/rx/desktop-acceptance.png"], check=True)
    print(json.dumps({"phase": phase, "passed": True, "real_graphics": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("initial", "resume", "safe"), required=True)
    try: main(parser.parse_args().phase)
    except Exception:
        subprocess.run(["scrot", "--overwrite", "/home/rx/desktop-acceptance.png"])
        logs = Path.home() / ".local/state/ruxeonrx"
        for path in sorted(logs.rglob("*.log")):
            if "snapshots" not in path.parts:
                print(str(path) + "\n" + path.read_text(errors="replace")[-4000:], file=sys.stderr)
        raise
