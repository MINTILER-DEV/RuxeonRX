"""Transactional native-manifest cache, updates, repair, and rollback support."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class PackageManager:
    def __init__(self, state_dir: Path, registry: Any) -> None:
        self.state_dir = state_dir
        self.registry = registry
        self.cache = state_dir / "package-cache"
        self.history_path = state_dir / "package-history.json"
        self.sources_path = state_dir / "sources.json"
        self.cache.mkdir(parents=True, exist_ok=True)

    def _read(self, path: Path, fallback: Any) -> Any:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback

    def _write(self, path: Path, value: Any) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def cache_manifest(self, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, str]:
        destination = self.cache / manifest["id"] / f'{manifest["version"]}.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(manifest_path.read_bytes())
        return {"path": str(destination), "sha256": self.digest(destination)}

    def install(self, manifest_path: Path) -> dict[str, Any]:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.registry._validate(manifest)
        record = self.registry.register(manifest)
        record["package"] = self.cache_manifest(manifest_path, record)
        self.registry.replace(record)
        return record

    def update(self, manifest_path: Path) -> dict[str, Any]:
        candidate = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.registry._validate(candidate)
        current = self.registry.get(candidate["id"])
        if current is None:
            raise KeyError(candidate["id"])
        if candidate["version"] == current["version"]:
            raise ValueError("update version is already installed")
        history = self._read(self.history_path, {})
        history.setdefault(candidate["id"], []).append(current)
        # Validate/cache before replacing registry state: errors cannot corrupt an install.
        candidate["launch_count"] = current.get("launch_count", 0)
        candidate["package"] = self.cache_manifest(manifest_path, candidate)
        self.registry.replace(candidate)
        self._write(self.history_path, history)
        return candidate

    def rollback(self, app_id: str) -> dict[str, Any]:
        history = self._read(self.history_path, {})
        entries = history.get(app_id, [])
        if not entries:
            raise ValueError("no rollback version is available")
        current = self.registry.get(app_id)
        previous = entries.pop()
        history[app_id] = entries
        if current is not None:
            entries.append(current)
        self.registry.replace(previous)
        self._write(self.history_path, history)
        return previous

    def repair(self, app_id: str) -> dict[str, Any]:
        current = self.registry.get(app_id)
        if current is None:
            raise KeyError(app_id)
        package = current.get("package", {})
        path = Path(package.get("path", ""))
        if not path.is_file() or package.get("sha256") != self.digest(path):
            raise ValueError("cached package is missing or has been modified")
        restored = json.loads(path.read_text(encoding="utf-8"))
        restored["launch_count"] = current.get("launch_count", 0)
        restored["package"] = package
        self.registry.replace(restored)
        return restored

    def add_source(self, name: str, url: str) -> dict[str, str]:
        sources = self._read(self.sources_path, {})
        sources[name] = url
        self._write(self.sources_path, sources)
        return {"name": name, "url": url}

    def sources(self) -> dict[str, str]:
        return self._read(self.sources_path, {})
