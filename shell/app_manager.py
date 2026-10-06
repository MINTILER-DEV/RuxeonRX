"""The app-management façade used by the RuxeonRX session and CLI."""
from __future__ import annotations

import json
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
from rx_packaged import PackageManager
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
        for handler in record.get("handlers", []):
            self.associations.set_default(handler, record["id"])
        self._log(record["id"], f"updated to version {record['version']}")
        return record

    def rollback(self, app_id: str) -> dict[str, Any]:
        record = self.packages.rollback(app_id)
        self._log(app_id, f"rolled back to version {record['version']}")
        return record

    def repair(self, app_id: str) -> dict[str, Any]:
        record = self.packages.repair(app_id)
        self._log(app_id, f"repaired version {record['version']}")
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
        roots = (self.log_root / app_id, self.state_dir / "data" / app_id)
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
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def remove(self, app_id: str, *, purge_data: bool = False) -> bool:
        if not self.registry.uninstall(app_id):
            return False
        self.portal.revoke_all(app_id)
        NotificationCenter(self.state_dir).clear_app(app_id)
        self.associations.remove_app(app_id)
        self._log(app_id, "app removed")
        if purge_data:
            log_dir = self.log_root / app_id
            if log_dir.exists():
                for child in log_dir.iterdir():
                    child.unlink()
                log_dir.rmdir()
        return True

    def _log(self, app_id: str, message: str) -> None:
        path = self.log_root / app_id / "activity.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
