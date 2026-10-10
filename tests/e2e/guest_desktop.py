"""Acceptance inside a real graphical QEMU guest; no fabricated ready signals."""
import argparse
import json
import os
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
    return subprocess.check_output(["xdotool", *args], text=True).strip()


def window(name):
    answer = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^" + name + "$"], capture_output=True, text=True)
    return answer.stdout.strip().splitlines()[0] if answer.returncode == 0 else None


def main(phase):
    runtime = Path(os.environ["RX_RUNTIME"])
    client = Client(runtime / "appd.sock")
    wait(lambda: (runtime / "graphical-ready").exists() and window("RuxeonRX Desktop"), "real Tk shell window")
    assert client.call("health")["healthy"]
    app_id = "org.ruxeonrx.native-test-app"
    if phase == "resume":
        apps = client.call("apps")
        app = next(item for item in apps if item["id"] == app_id)
        assert app["version"] == "0.2.0", "version did not persist across reboot"
        assert client.call("inspect", app_id=app_id)["permissions"]["notifications"] is True
        assert client.call("settings")["appearance.text_scale"] == 1.25
        client.call("launch", app_id=app_id)
        wait(lambda: window("RX Notes"), "native app relaunch after reboot")
        client.call("remove", app_id=app_id, purge_data=True)
        assert not client.call("apps", query="RX Notes")
        assert app_id not in client.call("defaults").values()
    else:
        shell = window("RuxeonRX Desktop")
        xdo("windowactivate", "--sync", shell)
        xdo("key", "--clearmodifiers", "ctrl+i")
        wait(lambda: client.call("apps", query="RX Notes"), "install from actual shell keyboard shortcut")
        xdo("key", "--clearmodifiers", "ctrl+l")
        notes = wait(lambda: window("RX Notes"), "real native Notes process and window")
        # Trigger notification by clicking the real application control.
        geometry = dict(line.split("=", 1) for line in xdo("getwindowgeometry", "--shell", notes).splitlines() if "=" in line)
        xdo("mousemove", str(int(geometry["X"]) + 245), str(int(geometry["Y"]) + 30)); xdo("click", "1")
        prompt = wait(lambda: window("RuxeonRX permission"), "user-visible portal permission prompt")
        xdo("windowactivate", "--sync", prompt); xdo("key", "alt+n")
        wait(lambda: client.call("inspect", app_id=app_id)["permissions"].get("notifications") is False, "denied notification")
        xdo("windowactivate", "--sync", notes)
        xdo("mousemove", str(int(geometry["X"]) + 245), str(int(geometry["Y"]) + 30)); xdo("click", "1")
        prompt = wait(lambda: window("RuxeonRX permission"), "second portal prompt")
        xdo("windowactivate", "--sync", prompt); xdo("key", "alt+y")
        wait(lambda: client.call("notifications"), "notification delivery after permission")
        client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.2.0"
        client.call("rollback", app_id=app_id)
        assert client.call("inspect", app_id=app_id)["app"]["version"] == "0.1.0"
        client.call("update", path=str(ROOT / "packages/catalog/rx-notes-0.2.0.rxpkg"))
        client.call("repair", app_id=app_id)
        client.call("set", key="appearance.text_scale", value=1.25)
        client.call("snapshot", name="acceptance-good")
        client.call("bundle", path="/home/rx/support-acceptance.zip")
    subprocess.run(["scrot", "/home/rx/desktop-acceptance.png"], check=True)
    print(json.dumps({"phase": phase, "passed": True, "real_graphics": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("initial", "resume"), required=True)
    main(parser.parse_args().phase)
