"""Notification inbox with portal-enforced delivery."""
from __future__ import annotations

import json
from pathlib import Path


class NotificationCenter:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "notifications.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def _write(self, entries: list[dict]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def post(self, app_id: str, title: str, body: str, permitted: bool) -> bool:
        if not permitted:
            return False
        entries = self._read()
        entries.append({"app_id": app_id, "title": title, "body": body})
        self._write(entries)
        return True

    def list(self) -> list[dict]:
        return self._read()

    def clear_app(self, app_id: str) -> None:
        self._write([entry for entry in self._read() if entry["app_id"] != app_id])
