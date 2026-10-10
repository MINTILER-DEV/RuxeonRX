#!/usr/bin/env python3
"""Build the two offline native packages and SHA-256 catalog."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "packages" / "catalog"
target.mkdir(parents=True, exist_ok=True)
entries = []
for version in ("0.1.0", "0.2.0"):
    manifest = json.loads((ROOT / "packages/native-test-app/manifest.json").read_text())
    manifest.update(version=version, launch={"command": ["python3", "{package}/main.py"]}, sandbox=True)
    manifest["name"] = "RX Notes"
    package = target / f"rx-notes-{version}.rxpkg"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.write(ROOT / "sdk/samples/desktop_app.py", "main.py")
        archive.write(ROOT / "sdk/bindings/python/rxipc.py", "rxipc.py")
    entries.append({"id": manifest["id"], "version": version, "url": package.resolve().as_uri(), "sha256": hashlib.sha256(package.read_bytes()).hexdigest()})
(target / "index.json").write_text(json.dumps({"format": 1, "packages": entries}, indent=2) + "\n")
print("Built offline catalog in " + str(target))
