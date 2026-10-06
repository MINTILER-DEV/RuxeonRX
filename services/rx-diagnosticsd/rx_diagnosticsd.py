"""Privacy-preserving support bundle generation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import zipfile

SECRET = re.compile(r"(?i)(token|password|secret|authorization)(\s*[:=]\s*)([^\s,]+)")
URL_SECRET = re.compile(r"(?i)([?&](?:token|key|secret)=)[^&\s\"]+")


class Diagnostics:
    def __init__(self, state_dir: Path, devices: dict) -> None:
        self.state_dir = state_dir
        self.devices = devices

    def scrub(self, text: str) -> str:
        home = str(Path.home())
        result = text.replace(home, "<home>") if home else text
        result = result.replace(str(self.state_dir), "<state>")
        username = os.environ.get("USERNAME") or os.environ.get("USER")
        if username:
            result = result.replace(username, "<user>")
        result = SECRET.sub(lambda match: match.group(1) + match.group(2) + "<redacted>", result)
        return URL_SECRET.sub(lambda match: match.group(1) + "<redacted>", result)

    def create(self, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = {"format": 1, "devices": self.devices, "included": []}
        allowed = ("apps.json", "permissions.json", "associations.json", "session.json", "settings.json", "sources.json")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in allowed:
                source = self.state_dir / name
                if source.is_file():
                    archive.writestr(f"state/{name}", self.scrub(source.read_text(encoding="utf-8")))
                    metadata["included"].append(f"state/{name}")
            log_root = self.state_dir / "diagnostics"
            if log_root.exists():
                for source in sorted(log_root.rglob("*.log")):
                    relative = source.relative_to(self.state_dir)
                    archive.writestr(str(relative).replace("\\", "/"), self.scrub(source.read_text(encoding="utf-8")))
                    metadata["included"].append(str(relative).replace("\\", "/"))
            archive.writestr("bundle.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        return target
