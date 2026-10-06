"""Validated shell, accessibility, input, privacy, and update preferences."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULTS = {
    "appearance.high_contrast": False,
    "appearance.text_scale": 1.0,
    "input.touchpad_natural_scroll": True,
    "input.focus_follows_mouse": False,
    "privacy.telemetry": False,
    "updates.channel": "stable",
}


class Settings:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "settings.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> dict:
        stored = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        return {**DEFAULTS, **stored}

    def set(self, key: str, value: object) -> dict:
        if key not in DEFAULTS:
            raise ValueError(f"unknown setting: {key}")
        expected = type(DEFAULTS[key])
        if expected is float:
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.75 <= float(value) <= 3.0:
                raise ValueError("text scale must be between 0.75 and 3.0")
            value = float(value)
        elif not isinstance(value, expected):
            raise ValueError(f"{key} requires {expected.__name__}")
        settings = self.all()
        settings[key] = value
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return settings
