"""Recoverable state snapshots with path-safe restore."""
from __future__ import annotations

from pathlib import Path
import shutil
import zipfile


class Recovery:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        self.snapshot_dir = self.state_dir / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create(self, name: str) -> Path:
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("snapshot name may contain letters, digits, hyphens, and underscores")
        target = self.snapshot_dir / f"{name}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.state_dir.rglob("*")):
                if path.is_file() and self.snapshot_dir not in path.parents:
                    archive.write(path, path.relative_to(self.state_dir))
        return target

    def restore(self, name: str) -> int:
        source = self.snapshot_dir / f"{name}.zip"
        if not source.is_file():
            raise ValueError("snapshot does not exist")
        restored = 0
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                relative = Path(member.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("unsafe snapshot member")
                target = (self.state_dir / relative).resolve()
                if self.state_dir not in target.parents:
                    raise ValueError("unsafe snapshot target")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                restored += 1
        return restored

    def list(self) -> list[str]:
        return [path.stem for path in sorted(self.snapshot_dir.glob("*.zip"))]
