#!/usr/bin/env python3
"""Single-writer desktop service plus a token-scoped application portal socket."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import selectors
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "shell")] + [str(path) for path in (ROOT / "services").iterdir() if path.is_dir()]
from app_manager import AppManager
from rx_notificationd import NotificationCenter
from rx_settingsd import Settings
from rx_deviced import DeviceInventory
from rx_diagnosticsd import Diagnostics
from rx_recoveryd import Recovery
from integration import sync_desktop


class DesktopService:
    def __init__(self, state, runtime):
        self.state = state
        self.runtime = runtime
        self.manager = AppManager(state)
        self.settings = Settings(state)
        self.notifications = NotificationCenter(state)
        self.tokens = {}
        self.requests = {}
        self.processes = {}
        self.mode = "safe" if (state / "safe-mode").exists() else "normal"

    def reap(self):
        for token, app_id in list(self.tokens.items()):
            process = self.processes.get(app_id)
            if process is None or process.poll() is not None:
                self.tokens.pop(token, None)

    def portal(self, method, params):
        self.reap()
        app_id = self.tokens.get(params.get("token"))
        if not app_id or self.manager.registry.get(app_id) is None:
            raise PermissionError("invalid application token")
        if method == "request":
            capability = params["capability"]
            app = self.manager.registry.get(app_id)
            if capability not in app["requested_permissions"] or capability not in ("files", "notifications"):
                raise PermissionError("undeclared or unsupported portal")
            if sum(item["app_id"] == app_id and item.get("pending") for item in self.requests.values()) >= 8:
                raise ValueError("too many pending portal requests")
            identifier = secrets.token_hex(16)
            self.requests[identifier] = {"id": identifier, "app_id": app_id, "capability": capability, "pending": True}
            return identifier
        if method == "result":
            request = self.requests.get(params["request_id"])
            if not request or request["app_id"] != app_id:
                raise PermissionError("unknown portal request")
            return request
        raise PermissionError("portal endpoint only accepts request/result")

    def dispatch(self, method, p):
        m = self.manager
        if method == "apps": return m.registry.list(p.get("query", ""))
        if method == "install": return m.install_manifest(Path(p["path"]))
        if method == "update": return m.update(Path(p["path"]))
        if method == "repair": return m.repair(p["app_id"])
        if method == "rollback": return m.rollback(p["app_id"])
        if method == "inspect": return m.inspect(p["app_id"])
        if method == "import": return m.import_desktop(Path(p["path"]))
        if method == "remove":
            process = self.processes.get(p["app_id"])
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            return m.remove(p["app_id"], purge_data=p.get("purge_data", False))
        if method == "launch":
            app_id = p["app_id"]
            app = m.registry.get(app_id)
            if app is None: raise ValueError("app is not installed")
            running = self.processes.get(app_id)
            if running and running.poll() is None:
                return {"pid": running.pid, "running": True}
            token = secrets.token_hex(32)
            env = {"RX_TOKEN": token, "RX_PORTAL_DIR": str(self.runtime / "portal")}
            if app.get("unrestricted"):
                import subprocess
                process = subprocess.Popen(m.launch(app_id), env={**os.environ, **env})
            else:
                process = m.execute(app_id, environment=env, sandbox=app.get("sandbox", False))
            self.processes[app_id] = process
            self.tokens[token] = app_id
            return {"pid": process.pid}
        if method == "decide":
            m.decide(p["app_id"], p["capability"], p["allowed"])
            return True
        if method == "pending": return [item for item in self.requests.values() if item.get("pending")]
        if method == "answer":
            request = self.requests[p["id"]]
            app_id, capability = request["app_id"], request["capability"]
            m.decide(app_id, capability, bool(p["allowed"]))
            answer = {**request, "pending": False, "message": "Permission denied"}
            if p["allowed"]:
                if capability == "files":
                    path = Path(p["path"])
                    if not path.is_file() or path.stat().st_size > 1024 * 1024:
                        raise ValueError("choose a regular text file smaller than 1 MiB")
                    granted = m.grant_file(app_id, path)
                    answer.update(content=Path(granted).read_text(encoding="utf-8", errors="replace"), message="Opened " + path.name)
                else:
                    self.notifications.post(app_id, "RX Notes", "Your notification was delivered through RuxeonRX.", True)
                    answer["message"] = "Notification delivered"
            self.requests[p["id"]] = answer
            return answer
        if method == "settings": return self.settings.all()
        if method == "set": return self.settings.set(p["key"], p["value"])
        if method == "notifications": return self.notifications.list()
        if method == "devices": return DeviceInventory().collect()
        if method == "defaults": return m.associations.defaults()
        if method == "open-with":
            app_id = m.associations.defaults().get(p["handler"])
            if not app_id: raise ValueError("no default application for handler")
            return self.dispatch("launch", {"app_id": app_id})
        if method == "default": return m.set_default_handler(p["app_id"], p["handler"])
        if method == "sources": return m.packages.sources()
        if method == "source": return m.packages.add_source(p["name"], p["url"])
        if method == "catalog": return m.packages.catalog(p["name"])
        if method == "source-install":
            result = m.packages.from_source(p["name"], p["app_id"], update=p.get("update", False))
            m.associations.remove_app(result["id"])
            for handler in result.get("handlers", []): m.associations.set_default(handler, result["id"])
            return result
        if method == "snapshot": return str(Recovery(self.state).create(p["name"]))
        if method == "snapshots": return Recovery(self.state).list()
        if method == "restore":
            for process in self.processes.values():
                if process.poll() is None: process.terminate(); process.wait(timeout=5)
            return Recovery(self.state).restore(p["name"])
        if method == "bundle": return str(Diagnostics(self.state, DeviceInventory().collect()).create(Path(p["path"])))
        if method == "health":
            self.reap()
            return {"healthy": True, "mode": self.mode, "pid": os.getpid(), "apps_running": [name for name, proc in self.processes.items() if proc.poll() is None]}
        raise ValueError("unknown method: " + method)


def serve(state, runtime):
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    (runtime / "portal").mkdir(exist_ok=True, mode=0o700)
    service = DesktopService(state, runtime)
    lock = (runtime / "writer.lock").open("a")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: raise RuntimeError("rx-appd already running for this session")
    selector = selectors.DefaultSelector()
    listeners = []
    for path, kind in ((runtime / "appd.sock", "admin"), (runtime / "portal/portal.sock", "portal")):
        if path.exists(): path.unlink()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path)); path.chmod(0o600); listener.listen(16)
        selector.register(listener, selectors.EVENT_READ, kind)
        listeners.append(listener)
    print("RX_APPD=ready", flush=True)
    try:
        while True:
            for key, _ in selector.select(timeout=1):
                conn, _ = key.fileobj.accept()
                with conn:
                    conn.settimeout(2)
                    try:
                        with conn.makefile("rb") as stream:
                            request = json.loads(stream.readline(1024 * 1024))
                        if request.get("version") != 1: raise ValueError("unsupported IPC version")
                        result = service.portal(request["method"], request.get("params", {})) if key.data == "portal" else service.dispatch(request["method"], request.get("params", {}))
                        if key.data == "admin" and request["method"] in ("install", "update", "repair", "rollback", "remove", "import", "restore", "source-install", "default"):
                            sync_desktop(service.manager)
                        answer = {"ok": True, "result": result}
                    except Exception as error:
                        answer = {"ok": False, "error": str(error)}
                    try: conn.sendall((json.dumps(answer) + "\n").encode())
                    except (BrokenPipeError, ConnectionResetError): pass
    finally:
        for process in service.processes.values():
            if process.poll() is None: process.terminate()
        for listener in listeners: listener.close()
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    serve(args.state, args.runtime)
