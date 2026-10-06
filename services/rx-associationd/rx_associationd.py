"""Persistent MIME/protocol default-handler registry owned by App Manager."""
from __future__ import annotations

import json
from pathlib import Path


class AssociationRegistry:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "associations.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, str]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def _write(self, records: dict[str, str]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def set_default(self, handler: str, app_id: str) -> None:
        records = self._read()
        records[handler] = app_id
        self._write(records)

    def defaults(self) -> dict[str, str]:
        return self._read()

    def remove_app(self, app_id: str) -> None:
        self._write({handler: owner for handler, owner in self._read().items() if owner != app_id})
