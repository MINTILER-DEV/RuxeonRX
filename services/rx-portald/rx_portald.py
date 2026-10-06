"""Persisted, capability-scoped portal decisions for the first vertical slice."""
from __future__ import annotations

import json
from pathlib import Path

VALID_CAPABILITIES = {"files", "notifications", "camera", "microphone", "location", "clipboard", "screen-capture", "network", "background"}


class Portal:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "permissions.json"
        self.grants_path = state_dir / "file-grants.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict[str, bool]]:
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def decide(self, app_id: str, capability: str, allowed: bool) -> None:
        if capability not in VALID_CAPABILITIES:
            raise ValueError(f"unknown capability: {capability}")
        decisions = self._read()
        decisions.setdefault(app_id, {})[capability] = allowed
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(decisions, indent=2, sort_keys=True) + "\n")
        temporary.replace(self.path)

    def allowed(self, app_id: str, capability: str) -> bool:
        return self._read().get(app_id, {}).get(capability, False)

    def decisions(self, app_id: str) -> dict[str, bool]:
        return self._read().get(app_id, {})

    def revoke_all(self, app_id: str) -> None:
        decisions = self._read()
        if app_id in decisions:
            del decisions[app_id]
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(decisions, indent=2, sort_keys=True) + "\n")
            temporary.replace(self.path)
        grants = self._read_grants()
        if app_id in grants:
            del grants[app_id]
            self._write_grants(grants)

    def _read_grants(self) -> dict[str, list[str]]:
        return json.loads(self.grants_path.read_text(encoding="utf-8")) if self.grants_path.exists() else {}

    def _write_grants(self, grants: dict[str, list[str]]) -> None:
        temporary = self.grants_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(grants, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.grants_path)

    def grant_file(self, app_id: str, path: Path) -> str:
        if not self.allowed(app_id, "files"):
            raise PermissionError("file permission has not been granted")
        resolved = str(path.expanduser().resolve())
        grants = self._read_grants()
        grants.setdefault(app_id, [])
        if resolved not in grants[app_id]:
            grants[app_id].append(resolved)
            self._write_grants(grants)
        return resolved

    def file_grants(self, app_id: str) -> list[str]:
        return self._read_grants().get(app_id, [])
