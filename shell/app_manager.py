"""The app-management façade used by the RuxeonRX session and CLI."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "rx-appd"))
sys.path.insert(0, str(ROOT / "services" / "rx-portald"))
sys.path.insert(0, str(ROOT / "services" / "rx-notificationd"))
sys.path.insert(0, str(ROOT / "services" / "rx-packaged"))
sys.path.insert(0, str(ROOT / "services" / "rx-associationd"))
from rx_appd import AppRegistry
from rx_portald import Portal
from rx_notificationd import NotificationCenter
from payloads import PackageManager
from rx_associationd import AssociationRegistry


class AppManager:
    """One user-facing owner for installation, launch history, inspection and removal."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.registry = AppRegistry(state_dir)
        self.portal = Portal(state_dir)
        self.log_root = state_dir / "diagnostics"
        self.packages = PackageManager(state_dir, self.registry)
        self.associations = AssociationRegistry(state_dir)

    def install_manifest(self, manifest_path: Path) -> dict[str, Any]:
        record = self.packages.install(manifest_path)
        for handler in record.get("handlers", []):
            self.associations.set_default(handler, record["id"])
        self._log(record["id"], f"installed version {record['version']}")
        return record

    def update(self, manifest_path: Path) -> dict[str, Any]:
        record = self.packages.update(manifest_path)
        self.associations.remove_app(record["id"])
        for capability in list(self.portal.decisions(record["id"])):
            if capability not in record["requested_permissions"]:
                self.portal.decide(record["id"], capability, False)
        for handler in record.get("handlers", []):
            self.associations.set_default(handler, record["id"])
        self._log(record["id"], f"updated to version {record['version']}")
        return record

    def rollback(self, app_id: str) -> dict[str, Any]:
        record = self.packages.rollback(app_id)
        self.associations.remove_app(app_id)
        for handler in record.get("handlers", []):
            self.associations.set_default(handler, app_id)
        self._log(app_id, f"rolled back to version {record['version']}")
        return record

    def repair(self, app_id: str) -> dict[str, Any]:
        record = self.packages.repair(app_id)
        self._log(app_id, f"repaired version {record['version']}")
        return record

    def execute(self, app_id: str, *, environment=None, sandbox=False) -> subprocess.Popen:
        app = self.registry.get(app_id)
        if app is None:
            raise KeyError(app_id)
        if app.get("unrestricted"):
            command = self.launch(app_id)
        else:
            self.packages.verify(app)
            command = [part.replace("{package}", app["package"]["root"]) for part in self.launch(app_id)]
        data_dir = self.state_dir / "data" / app_id
        data_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **(environment or {}), "RX_APP_ID": app_id, "RX_APP_NAME": app["name"], "RX_DATA_DIR": str(data_dir)}
        if sandbox:
            if not shutil.which("bwrap"):
                raise RuntimeError("bubblewrap is required for sandboxed packages")
            prefix = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--share-net" if "network" in app["requested_permissions"] and self.portal.allowed(app_id, "network") else "--unshare-net", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--ro-bind", "/etc", "/etc", "--ro-bind", app["package"]["root"], app["package"]["root"], "--bind", str(data_dir), str(data_dir), "--ro-bind", "/tmp/.X11-unix", "/tmp/.X11-unix", "--ro-bind", env["RX_PORTAL_DIR"], env["RX_PORTAL_DIR"], "--setenv", "HOME", str(data_dir)]
            authority = env.get("XAUTHORITY", str(Path.home() / ".Xauthority"))
            if Path(authority).is_file():
                prefix += ["--ro-bind", authority, authority, "--setenv", "XAUTHORITY", authority]
            command = prefix + command
        log_dir = self.log_root / app_id
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "process.log").open("ab") as output:
            process = subprocess.Popen(command, cwd=data_dir, env=env, stdout=output, stderr=subprocess.STDOUT)
        self._log(app_id, f"process started: {process.pid}")
        return process

    def import_desktop(self, path: Path) -> dict:
        import configparser
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(path, encoding="utf-8")
        entry = parser["Desktop Entry"]
        if entry.get("Type") != "Application":
            raise ValueError("desktop entry is not an application")
        command = [part for part in shlex.split(entry["Exec"]) if not part.startswith("%")]
        app_id = "org.ruxeonrx.import." + path.stem.lower().replace("_", "-")
        record = {"id": app_id, "name": entry.get("Name", path.stem), "version": "1", "source": "desktop-entry", "runtime_kind": "native-linux", "package_kind": "desktop-entry", "launch": {"command": command}, "requested_permissions": ["files", "notifications"], "data_dir": "data/" + app_id, "diagnostics_dir": "diagnostics/" + app_id, "handlers": [value for value in entry.get("MimeType", "").split(";") if value and not value.startswith("x-scheme-handler")], "unrestricted": True}
        for key in ("Icon", "StartupWMClass"):
            if any(character in entry.get(key, "") for character in ("\r", "\n", "\x00")): raise ValueError("invalid desktop integration metadata")
        record.update(desktop_icon=entry.get("Icon", "application-x-executable"), startup_wm_class=entry.get("StartupWMClass", path.stem))
        self.registry.register(record)
        for handler in record["handlers"]:
            self.associations.set_default(handler, app_id)
        return record

    def launch(self, app_id: str) -> list[str]:
        app = self.registry.get(app_id)
        if app is None:
            raise KeyError(app_id)
        self._log(app_id, "launch requested: " + " ".join(app["launch"]["command"]))
        self.registry.record_launch(app_id)
        return app["launch"]["command"]

    def decide(self, app_id: str, capability: str, allowed: bool) -> None:
        app = self.registry.get(app_id)
        if app is None:
            raise KeyError(app_id)
        if capability not in app["requested_permissions"]:
            raise PermissionError(f"{app_id} did not request {capability}")
        self.portal.decide(app_id, capability, allowed)
        self._log(app_id, f"permission {capability}: {'allowed' if allowed else 'denied'}")

    def inspect(self, app_id: str) -> dict[str, Any]:
        app = self.registry.get(app_id)
        if app is None:
            raise KeyError(app_id)
        return {"app": app, "permissions": self.portal.decisions(app_id), "file_grants": self.portal.file_grants(app_id), "logs": self.logs(app_id), "storage_bytes": self.storage_bytes(app_id)}

    def storage_bytes(self, app_id: str) -> int:
        roots = (self.log_root / app_id, self.state_dir / "data" / app_id, self.state_dir / "package-cache" / app_id)
        return sum(path.stat().st_size for root in roots if root.exists() for path in root.rglob("*") if path.is_file())

    def grant_file(self, app_id: str, path: Path) -> str:
        if self.registry.get(app_id) is None:
            raise KeyError(app_id)
        granted = self.portal.grant_file(app_id, path)
        self._log(app_id, f"file grant: {granted}")
        return granted

    def set_default_handler(self, app_id: str, handler: str) -> None:
        app = self.registry.get(app_id)
        if app is None:
            raise KeyError(app_id)
        if handler not in app.get("handlers", []):
            raise ValueError(f"{app_id} does not declare {handler}")
        self.associations.set_default(handler, app_id)

    def logs(self, app_id: str) -> list[str]:
        path = self.log_root / app_id / "activity.log"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        process = self.log_root / app_id / "process.log"
        if process.exists(): lines += process.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines

    def remove(self, app_id: str, *, purge_data: bool = False) -> bool:
        app = self.registry.get(app_id)
        if app is None: return False
        if not self.registry.uninstall(app_id):
            return False
        self.portal.revoke_all(app_id)
        NotificationCenter(self.state_dir).clear_app(app_id)
        self.associations.remove_app(app_id)
        self._log(app_id, "app removed")
        if purge_data:
            for directory in (self.log_root / app_id, self.state_dir / "data" / app_id, self.state_dir / "package-cache" / app_id):
                if directory.is_symlink():
                    directory.unlink()
                elif directory.exists():
                    shutil.rmtree(directory)
            for record in [app] + app.get("history", []):
                blob = Path(record.get("package", {}).get("blob", ""))
                if blob.is_file() and blob.parent.resolve() == (self.state_dir / "package-cache").resolve(): blob.unlink()
        return True

    def _log(self, app_id: str, message: str) -> None:
        path = self.log_root / app_id / "activity.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
