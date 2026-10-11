"""The small, explicit Stage 1 app-registry contract."""
from __future__ import annotations

import json
import re
import os
import shutil
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
        if not self.path.exists(): return {}
        def decode(path):
            records = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records, dict): raise ValueError("invalid registry structure")
            for identifier, record in records.items():
                self._validate(record)
                if identifier != record["id"]: raise ValueError("registry identity mismatch")
            return records
        try: return decode(self.path)
        except (ValueError, TypeError):
            backup = self.path.with_suffix(".backup")
            if not backup.exists(): raise ValueError("registry corrupt; restore a recovery snapshot")
            try: restored = decode(backup)
            except (ValueError, TypeError): raise ValueError("registry and backup corrupt; restore a recovery snapshot")
            shutil.copyfile(self.path, self.path.with_suffix(".corrupt"))
            shutil.copyfile(backup, self.path)
            (self.path.parent / "safe-mode").touch()
            return restored

    def _write(self, records: dict[str, dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(".tmp")
        if self.path.exists(): shutil.copyfile(self.path, self.path.with_suffix(".backup"))
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(records, indent=2, sort_keys=True) + "\n")
            handle.flush(); os.fsync(handle.fileno())
        temporary.replace(self.path)

    @staticmethod
    def _validate(manifest: dict[str, Any]) -> None:
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
        missing = REQUIRED - manifest.keys()
        if missing:
            raise ValueError(f"manifest missing: {', '.join(sorted(missing))}")
        if not isinstance(manifest["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", manifest["id"]):
            raise ValueError("invalid app ID")
        if not isinstance(manifest["version"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", manifest["version"]):
            raise ValueError("invalid version")
        for field in ("name", "source", "data_dir", "diagnostics_dir"):
            if not isinstance(manifest[field], str) or not manifest[field].strip():
                raise ValueError(f"invalid {field}")
            if any(character in manifest[field] for character in ("\x00", "\r", "\n")):
                raise ValueError(f"invalid control character in {field}")
        if manifest["runtime_kind"] not in RUNTIMES:
            raise ValueError("unknown runtime kind")
        if manifest["package_kind"] not in {"deb", "portable", "desktop-entry", "test"}:
            raise ValueError("unknown package kind")
        if "sandbox" in manifest and not isinstance(manifest["sandbox"], bool):
            raise ValueError("sandbox must be a boolean")
        if "icon" in manifest and (not isinstance(manifest["icon"], str) or Path(manifest["icon"]).is_absolute() or ".." in Path(manifest["icon"]).parts or "\\" in manifest["icon"] or ":" in manifest["icon"]):
            raise ValueError("icon must be a relative payload path")
        if not isinstance(manifest["requested_permissions"], list):
            raise ValueError("requested_permissions must be a list")
        if not isinstance(manifest["launch"], dict) or not isinstance(manifest["launch"].get("command"), list) or not manifest["launch"]["command"] or not all(isinstance(item, str) and item and "\x00" not in item for item in manifest["launch"]["command"]):
            raise ValueError("launch.command must be a non-empty list")
        allowed = {"files", "notifications", "camera", "microphone", "location", "clipboard", "screen-capture", "network", "background"}
        if any(not isinstance(item, str) or item not in allowed for item in manifest["requested_permissions"]):
            raise ValueError("unknown permission")
        if not isinstance(manifest.get("handlers", []), list) or any(not isinstance(item, str) or not re.fullmatch(r"(?:[a-z]+/[a-z0-9.+-]+|[a-z][a-z0-9+.-]*:)", item) for item in manifest.get("handlers", [])):
            raise ValueError("invalid handler")

    def register(self, manifest: dict[str, Any]) -> dict[str, Any]:
        self._validate(manifest)
        records = self._read()
        record = dict(manifest)
        previous = records.get(manifest["id"], {})
        record["launch_count"] = previous.get("launch_count", 0)
        records[manifest["id"]] = record
        self._write(records)
        return record

    def replace(self, record: dict[str, Any]) -> None:
        """Commit a fully validated record as one atomic state transition."""
        self._validate(record)
        records = self._read()
        records[record["id"]] = record
        self._write(records)

    def list(self, query: str = "") -> list[dict[str, Any]]:
        needle = query.casefold()
        return [record for record in self._read().values() if needle in record["name"].casefold() or needle in record["id"].casefold()]

    def get(self, app_id: str) -> dict[str, Any] | None:
        return self._read().get(app_id)

    def record_launch(self, app_id: str) -> None:
        records = self._read()
        if app_id not in records:
            raise KeyError(app_id)
        records[app_id]["launch_count"] = records[app_id].get("launch_count", 0) + 1
        self._write(records)

    def uninstall(self, app_id: str) -> bool:
        records = self._read()
        if app_id not in records:
            return False
        del records[app_id]
        self._write(records)
        return True
