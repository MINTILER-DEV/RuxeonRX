#!/usr/bin/env python3
"""Build sandboxed and regular native samples and the SHA-256 catalog."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "packages" / "catalog"
target.mkdir(parents=True, exist_ok=True)
entries = []
for version, sandbox in (("0.1.0", True), ("0.2.0", True), ("0.1.0", False)):
    manifest = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
    manifest.update(version=version, launch={"command": ["python3", "{package}/main.py"]}, sandbox=sandbox, icon="notes.svg")
    manifest["name"] = "RX Notes"
    if not sandbox:
        manifest.update(id="org.ruxeonrx.regular-notes", name="RX Notes Native", handlers=[])
    package = target / f"{'rx-notes' if sandbox else 'rx-notes-native'}-{version}.rxpkg"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.write(ROOT / "sdk/samples/desktop_app.py", "main.py")
        archive.write(ROOT / "sdk/bindings/python/rxipc.py", "rxipc.py")
        archive.write(ROOT / "shell/assets/notes.svg", "notes.svg")
    entries.append({"id": manifest["id"], "version": version, "url": package.resolve().as_uri(), "sha256": hashlib.sha256(package.read_bytes()).hexdigest()})
(target / "index.json").write_text(json.dumps({"format": 1, "packages": entries}, indent=2) + "\n")
print("Built offline catalog in " + str(target))
