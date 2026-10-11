#!/usr/bin/env python3
"""Single-writer desktop service plus a token-scoped application portal socket."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import selectors
import socket
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "shell")] + [str(path) for path in (ROOT / "services").iterdir() if path.is_dir()]
from app_manager import AppManager
from rx_notificationd import NotificationCenter
from rx_settingsd import Settings
from rx_deviced import DeviceInventory
from rx_diagnosticsd import Diagnostics
from rx_recoveryd import Recovery
from integration import sync_desktop
from system_integration import active, apply_settings, import_core_apps, sync_favorites, reconcile_favorites


class DesktopService:
    def __init__(self, state, runtime):
        self.state = state
        self.runtime = runtime
        self.manager = AppManager(state)
        if not (state / "safe-mode").exists() and not self.manager.packages.sources():
            catalog = ROOT / "packages/catalog/index.json"
            if catalog.exists(): self.manager.packages.add_source("ruxeonrx-samples", catalog.as_uri())
        self.settings = Settings(state)
        self.notifications = NotificationCenter(state)
        self.tokens = {}
        self.requests = {}
        self.processes = {}
        self.mode = "safe" if (state / "safe-mode").exists() else "normal"
        if self.mode == "normal":
            import_core_apps(self.manager)
            if active(): sync_desktop(self.manager)
            apply_settings(self.settings.all())

    def reap(self):
        for token, app_id in list(self.tokens.items()):
            process = self.processes.get(app_id)
            if process is None or process.poll() is not None:
                self.tokens.pop(token, None)
                self.requests = {key: item for key, item in self.requests.items() if item["app_id"] != app_id}

    def file_intent(self, app_id, filename):
        app = self.manager.registry.get(app_id)
        if sum(item["app_id"] == app_id for item in self.requests.values()) >= 16:
            raise ValueError("too many unconsumed open requests")
        uri = urlparse(str(filename))
        if uri.scheme and uri.scheme != "file":
            if uri.scheme + ":" not in app.get("handlers", []):
                raise ValueError("application does not declare this protocol")
            identifier = secrets.token_hex(16)
            self.requests[identifier] = {"id": identifier, "app_id": app_id, "pending": False, "origin": "open-with", "content": str(filename), "message": "Opened link"}
            return identifier
        if uri.scheme == "file":
            if uri.netloc not in ("", "localhost"): raise ValueError("remote file URIs are unsupported")
            filename = unquote(uri.path)
        path = Path(filename).expanduser().resolve()
        if "files" not in app["requested_permissions"]:
            raise PermissionError("application does not support the file portal")
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("choose a regular text file smaller than 1 MiB")
        identifier = secrets.token_hex(16)
        self.requests[identifier] = {"id": identifier, "app_id": app_id, "capability": "files", "pending": True, "origin": "open-with", "suggested_path": str(path)}
        return identifier

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
            if not request.get("pending"): self.requests.pop(params["request_id"])
            return request
        if method == "intents":
            return [{"id": item["id"]} for item in self.requests.values() if item["app_id"] == app_id and item.get("origin") == "open-with"]
        raise PermissionError("portal endpoint only accepts request/result")

    def dispatch(self, method, p):
        m = self.manager
        if method == "apps":
            if self.mode == "normal": reconcile_favorites(m)
            return m.registry.list(p.get("query", ""))
        if method == "install": return m.install_manifest(Path(p["path"]))
        if method == "update": return m.update(Path(p["path"]))
        if method == "repair": return m.repair(p["app_id"])
        if method == "rollback": return m.rollback(p["app_id"])
        if method == "inspect": return m.inspect(p["app_id"])
        if method == "pin":
            app = m.registry.get(p["app_id"])
            if app is None: raise ValueError("app is not installed")
            app["pinned"] = bool(p["pinned"])
            m.registry.replace(app)
            sync_favorites(m.registry.list())
            return app
        if method == "reset-data":
            app_id = p["app_id"]
            if m.registry.get(app_id) is None: raise ValueError("app is not installed")
            process = self.processes.get(app_id)
            if process and process.poll() is None: process.terminate(); process.wait(timeout=5)
            import shutil
            data = self.state / "data" / app_id
            if data.exists(): shutil.rmtree(data)
            data.mkdir(parents=True)
            m._log(app_id, "managed app data reset")
            return True
        if method == "import": return m.import_desktop(Path(p["path"]))
        if method == "remove":
            process = self.processes.get(p["app_id"])
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            self.tokens = {token: app_id for token, app_id in self.tokens.items() if app_id != p["app_id"]}
            self.requests = {key: item for key, item in self.requests.items() if item["app_id"] != p["app_id"]}
            return m.remove(p["app_id"], purge_data=p.get("purge_data", False))
        if method == "launch":
            app_id = p["app_id"]
            app = m.registry.get(app_id)
            if app is None: raise ValueError("app is not installed")
            running = self.processes.get(app_id)
            if running and running.poll() is None and not (app.get("unrestricted") and p.get("path")):
                if p.get("path"): self.file_intent(app_id, p["path"])
                return {"pid": running.pid, "running": True}
            token = secrets.token_hex(32)
            env = {"RX_TOKEN": token, "RX_PORTAL_DIR": str(self.runtime / "portal")}
            process = m.execute(app_id, environment=env, sandbox=app.get("sandbox", False), intent=p.get("path") if app.get("unrestricted") else None)
            self.processes[app_id] = process
            self.tokens[token] = app_id
            if p.get("path") and not app.get("unrestricted"): self.file_intent(app_id, p["path"])
            return {"pid": process.pid}
        if method == "decide":
            m.decide(p["app_id"], p["capability"], p["allowed"])
            return True
        if method == "pending":
            self.reap()
            return [item for item in self.requests.values() if item.get("pending")]
        if method == "answer":
            request = self.requests[p["id"]]
            app_id, capability = request["app_id"], request["capability"]
            answer = {**request, "pending": False, "message": "Permission denied"}
            content = None
            if p["allowed"] and capability == "files":
                path = Path(p["path"])
                if not path.is_file() or path.stat().st_size > 1024 * 1024:
                    raise ValueError("choose a regular text file smaller than 1 MiB")
                content = path.read_text(encoding="utf-8", errors="replace")
            m.decide(app_id, capability, bool(p["allowed"]))
            if p["allowed"]:
                if capability == "files":
                    m.grant_file(app_id, path)
                    answer.update(content=content, message="Opened " + path.name)
                else:
                    self.notifications.post(app_id, m.registry.get(app_id)["name"], "Your notification was delivered through RuxeonRX.", True)
                    answer["message"] = "Notification delivered"
            self.requests[p["id"]] = answer
            return answer
        if method == "settings": return self.settings.all()
        if method == "set":
            settings = self.settings.set(p["key"], p["value"])
            apply_settings(settings)
            return settings
        if method == "notifications": return self.notifications.list()
        if method == "devices": return DeviceInventory().collect()
        if method == "defaults": return m.associations.defaults()
        if method == "open-with":
            app_id = m.associations.defaults().get(p["handler"])
            if not app_id: raise ValueError("no default application for handler")
            return self.dispatch("launch", {"app_id": app_id, "path": p.get("path")})
        if method == "default": return m.set_default_handler(p["app_id"], p["handler"])
        if method == "sources": return m.packages.sources()
        if method == "updates":
            result = []
            for app in m.registry.list():
                if app["source"] in m.packages.sources():
                    matches = [item for item in m.packages.catalog(app["source"]) if item["id"] == app["id"]]
                    if matches and matches[-1].get("version") != app["version"]:
                        result.append({"app_id": app["id"], "source": app["source"], "installed": app["version"], "available": matches[-1].get("version")})
            return result
        if method == "source": return m.packages.add_source(p["name"], p["url"])
        if method == "catalog": return m.packages.catalog(p["name"])
        if method == "source-install":
            result = m.packages.from_source(p["name"], p["app_id"], update=p.get("update", False))
            m.associations.remove_app(result["id"])
            for capability in list(m.portal.decisions(result["id"])):
                if capability not in result["requested_permissions"]: m.portal.decide(result["id"], capability, False)
            for handler in result.get("handlers", []): m.associations.set_default(handler, result["id"])
            return result
        if method == "snapshot": return str(Recovery(self.state).create(p["name"]))
        if method == "snapshots": return Recovery(self.state).list()
        if method == "restore":
            for process in self.processes.values():
                if process.poll() is None: process.terminate(); process.wait(timeout=5)
            result = Recovery(self.state).restore(p["name"])
            self.tokens.clear(); self.requests.clear()
            apply_settings(self.settings.all())
            sync_favorites(m.registry.list())
            return result
        if method == "bundle": return str(Diagnostics(self.state, DeviceInventory().collect()).create(Path(p["path"])))
        if method == "health":
            self.reap()
            services = {"rx-appd": os.getpid()}
            session_path = self.state / "session.json"
            if session_path.is_file():
                try: services.update(json.loads(session_path.read_text()).get("pids", {}))
                except json.JSONDecodeError: pass
            alive = {}
            for name, pid in services.items():
                try: os.kill(pid, 0); alive[name] = True
                except (ProcessLookupError, PermissionError): alive[name] = False
            return {"healthy": all(alive.values()), "mode": "safe" if (self.state / "safe-mode").exists() else "normal", "pid": os.getpid(), "services": alive, "apps_running": [name for name, proc in self.processes.items() if proc.poll() is None]}
        raise ValueError("unknown method: " + method)


def serve(state, runtime):
    def terminate(*unused):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
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
        for process in service.processes.values():
            try: process.wait(timeout=5)
            except Exception: process.kill(); process.wait()
        for listener in listeners: listener.close()
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    serve(args.state, args.runtime)
