"""Validated immutable native payloads; history and registry commit atomically."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
import urllib.request
import zipfile
from rx_packaged import PackageManager as LegacyPackageManager


class PackageManager(LegacyPackageManager):
    def _prepare(self, source: Path) -> dict:
        if source.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("package exceeds 32 MiB alpha limit")
        with tempfile.TemporaryDirectory(dir=self.cache) as temporary:
            staging = Path(temporary)
            if zipfile.is_zipfile(source):
                with zipfile.ZipFile(source) as archive:
                    if sum(item.file_size for item in archive.infolist()) > 64 * 1024 * 1024:
                        raise ValueError("expanded package exceeds size limit")
                    for item in archive.infolist():
                        relative = Path(item.filename)
                        if relative.is_absolute() or ".." in relative.parts or "\\" in item.filename or ":" in item.filename or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                            raise ValueError("unsafe package entry")
                    archive.extractall(staging)
                    for item in archive.infolist():
                        payload = staging / item.filename
                        if payload.is_file() and (item.external_attr >> 16) & 0o111:
                            # Preserve executability, never setuid/setgid archive bits.
                            payload.chmod(0o700)
                manifest = self._read(staging / "manifest.json", None)
            else:
                manifest = json.loads(source.read_text(encoding="utf-8"))
                shutil.copyfile(source, staging / "manifest.json")
            self.registry._validate(manifest)
            for part in manifest["launch"]["command"]:
                if part.startswith("{package}/"):
                    relative = Path(part[len("{package}/"):])
                    candidate = staging / relative
                    if ".." in relative.parts or not candidate.is_file():
                        raise ValueError("launch payload does not exist")
                    if candidate.suffix == ".py":
                        try: compile(candidate.read_text(encoding="utf-8"), str(relative), "exec")
                        except SyntaxError as error: raise ValueError("invalid Python payload: " + str(error))
            hashes = {str(path.relative_to(staging)).replace("\\", "/"): self.digest(path) for path in staging.rglob("*") if path.is_file()}
            identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
            destination = self.cache / manifest["id"] / (manifest["version"] + "-" + identity[:16])
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copytree(staging, destination)
            manifest["package"] = {"path": str(destination / "manifest.json"), "sha256": hashes["manifest.json"], "root": str(destination), "hashes": hashes}
            blob = self.cache / (self.digest(source) + ".blob")
            if not blob.exists(): shutil.copyfile(source, blob)
            manifest["package"].update(blob=str(blob), blob_sha256=self.digest(source))
            manifest["data_dir"] = str(self.state_dir / "data" / manifest["id"])
            manifest["diagnostics_dir"] = str(self.state_dir / "diagnostics" / manifest["id"])
            self.verify(manifest)
            return manifest

    def install(self, source):
        record = self._prepare(source)
        if self.registry.get(record["id"]) is not None:
            raise ValueError("app already installed; use update")
        record.update(launch_count=0, history=[])
        self.registry.replace(record)
        return record

    def update(self, source):
        record = self._prepare(source)
        current = self.registry.get(record["id"])
        if current is None:
            raise KeyError(record["id"])
        if record["version"] == current["version"]:
            raise ValueError("update version is already installed")
        previous = {key: value for key, value in current.items() if key != "history"}
        record["history"] = current.get("history", []) + [previous]
        record["launch_count"] = current.get("launch_count", 0)
        record["pinned"] = current.get("pinned", False)
        self.registry.replace(record)
        return record

    def verify(self, record):
        package = record.get("package", {})
        root = Path(package.get("root", ""))
        if self.cache.resolve() not in root.resolve().parents:
            raise ValueError("package path is outside managed cache")
        if not package.get("hashes"):
            raise ValueError("app has no verified package payload")
        for relative, expected in package["hashes"].items():
            path = root / relative
            if root.resolve() not in path.resolve().parents:
                raise ValueError("package path escapes cache")
            if not path.is_file() or path.is_symlink() or self.digest(path) != expected:
                raise ValueError("package is missing or modified: " + relative)

    def rollback(self, app_id):
        current = self.registry.get(app_id)
        if current is None:
            raise KeyError(app_id)
        entries = list(current.get("history", []))
        if not entries:
            raise ValueError("no rollback version is available")
        previous = dict(entries.pop())
        if previous.get("id") != app_id:
            raise ValueError("rollback history identity mismatch")
        self.verify(previous)
        previous["history"] = entries
        previous["launch_count"] = current.get("launch_count", 0)
        previous["pinned"] = current.get("pinned", False)
        self.registry.replace(previous)
        return previous

    def repair(self, app_id):
        current = self.registry.get(app_id)
        if current is None:
            raise KeyError(app_id)
        package = current.get("package", {})
        blob = Path(package.get("blob", ""))
        if not blob.is_file() or self.digest(blob) != package.get("blob_sha256"):
            raise ValueError("repair archive is missing or modified; re-download from a trusted source")
        root = Path(package["root"]).resolve()
        if self.cache.resolve() not in root.parents:
            raise ValueError("invalid repair target")
        if root.exists(): shutil.rmtree(root)
        restored = self._prepare(blob)
        self.verify(restored)
        restored.update({key: current[key] for key in ("history", "launch_count", "pinned") if key in current})
        self.registry.replace(restored)
        return restored

    def add_source(self, name, url):
        if urlparse(url).scheme not in ("https", "file"):
            raise ValueError("sources require HTTPS or a local file URL")
        return super().add_source(name, url)

    def catalog(self, name):
        url = self.sources().get(name)
        if not url:
            raise ValueError("source not found")
        with urllib.request.urlopen(url, timeout=15) as response:
            catalog = json.loads(response.read(1024 * 1024))
        if catalog.get("format") != 1 or not isinstance(catalog.get("packages"), list):
            raise ValueError("invalid source catalog")
        return catalog["packages"]

    def from_source(self, name, app_id, *, update=False):
        entry = next((item for item in reversed(self.catalog(name)) if item.get("id") == app_id), None)
        if entry is None:
            raise ValueError("app not in source")
        if urlparse(entry["url"]).scheme not in ("https", "file"):
            raise ValueError("invalid package URL")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "download.rxpkg"
            with urllib.request.urlopen(entry["url"], timeout=30) as response:
                data = response.read(32 * 1024 * 1024 + 1)
            source.write_bytes(data)
            if self.digest(source) != entry["sha256"]:
                raise ValueError("source checksum mismatch")
            prepared = self._prepare(source)
            if prepared["id"] != app_id or (entry.get("version") and prepared["version"] != entry["version"]):
                raise ValueError("source package identity does not match catalog")
            return self.update(source) if update else self.install(source)
