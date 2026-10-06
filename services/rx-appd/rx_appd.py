"""The small, explicit Stage 1 app-registry contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED = {"id", "name", "version", "source", "package_kind", "runtime_kind", "launch", "data_dir", "diagnostics_dir", "requested_permissions"}
RUNTIMES = {"native-linux", "windows", "android", "web", "vm"}


class AppRegistry:
    """Single writer for normalized records, backed by an atomic JSON file."""

    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "apps.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict[str, Any]]:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def _write(self, records: dict[str, dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
        temporary.replace(self.path)

    @staticmethod
    def _validate(manifest: dict[str, Any]) -> None:
        missing = REQUIRED - manifest.keys()
        if missing:
            raise ValueError(f"manifest missing: {', '.join(sorted(missing))}")
        if manifest["runtime_kind"] not in RUNTIMES:
            raise ValueError("unknown runtime kind")
        if not isinstance(manifest["launch"].get("command"), list) or not manifest["launch"]["command"]:
            raise ValueError("launch.command must be a non-empty list")

    def register(self, manifest: dict[str, Any]) -> dict[str, Any]:
        self._validate(manifest)
        records = self._read()
        records[manifest["id"]] = manifest
        self._write(records)
        return manifest

    def list(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.casefold()
        return [record for record in self._read().values() if needle in record["name"].casefold() or needle in record["id"].casefold()]

    def get(self, app_id: str) -> dict[str, Any] | None:
        return self._read().get(app_id)

    def uninstall(self, app_id: str) -> bool:
        records = self._read()
        if app_id not in records:
            return False
        del records[app_id]
        self._write(records)
        return True
