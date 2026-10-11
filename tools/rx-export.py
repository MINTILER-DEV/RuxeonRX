#!/usr/bin/env python3
"""Export a frozen desktop disk with a checksum manifest, without SSH keys."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--disk", type=Path, default=ROOT / "out/desktop/ruxeonrx-1.0.qcow2")
    parser.add_argument("--manifest", type=Path, default=ROOT / "out/desktop/artifact.json")
    args = parser.parse_args()
    source = args.disk.resolve(); output = args.output.resolve()
    manifest_path = output.with_suffix(".json")
    staging = output.with_name(output.name + ".partial")
    if any(path.exists() for path in (output, manifest_path, staging)):
        parser.error("export target or staging file exists; choose a new output name")
    manifest = json.loads(args.manifest.read_text())
    original_hash = checksum(source)
    if original_hash != manifest["disk_sha256"]:
        parser.error("source disk changed since provisioning; regenerate its build manifest before exporting")
    output.parent.mkdir(parents=True, exist_ok=True)
    # QEMU's normal image locks reject a disk currently opened for writing.
    # A test overlay may read this immutable backing disk concurrently.
    subprocess.run(["qemu-img", "convert", "-c", "-O", "qcow2", str(source), str(staging)], check=True)
    if checksum(source) != original_hash:
        raise RuntimeError("source changed during export; incomplete staging disk preserved, no success manifest written")
    manifest.update(source_disk_sha256=original_hash, disk_sha256=checksum(staging), export_format="standalone-compressed-qcow2")
    staging.rename(output)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Exported " + str(output), flush=True)
    print("Manifest " + str(manifest_path), flush=True)


if __name__ == "__main__": main()
