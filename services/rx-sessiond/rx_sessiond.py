"""Session supervision, crash accounting, health, and safe-mode policy."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_SERVICES = ("rx-appd", "rx-portald", "rx-notificationd", "rx-settingsd", "rx-deviced")


class SessionSupervisor:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "session.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _default(self) -> dict:
        return {"mode": "normal", "crash_count": 0, "services": {name: "stopped" for name in REQUIRED_SERVICES}}

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else self._default()

    def _write(self, state: dict) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def start(self, *, safe_mode: bool = False) -> dict:
        state = self._read()
        state["mode"] = "safe" if safe_mode or state["crash_count"] >= 3 else "normal"
        state["services"] = {name: "running" for name in REQUIRED_SERVICES}
        self._write(state)
        return state

    def crash(self, service: str) -> dict:
        if service not in REQUIRED_SERVICES:
            raise ValueError(f"unknown service: {service}")
        state = self._read()
        state["services"][service] = "failed"
        state["crash_count"] += 1
        if state["crash_count"] >= 3:
            state["mode"] = "safe"
        self._write(state)
        return state

    def recover(self) -> dict:
        state = self._default()
        state["services"] = {name: "running" for name in REQUIRED_SERVICES}
        self._write(state)
        return state

    def health(self) -> dict:
        state = self._read()
        failed = [name for name, status in state["services"].items() if status != "running"]
        return {**state, "healthy": not failed, "failed_services": failed}
