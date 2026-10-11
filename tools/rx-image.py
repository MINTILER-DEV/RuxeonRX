#!/usr/bin/env python3
"""Build a complete desktop disk in an isolated QEMU builder, no host sudo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "desktop"


def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)


def wait_ssh(key, port, process, limit=600):
    deadline = time.monotonic() + limit
    args = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=3", "-i", str(key), "-p", str(port), "root@127.0.0.1"]
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("builder exited; inspect out/desktop/builder.log")
        if subprocess.run(args + ["true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return args
        time.sleep(2)
    raise TimeoutError("SSH boot timed out")


def build(args):
    required = ("qemu-img", "qemu-system-x86_64", "ssh", "scp", "ssh-keygen") + (() if args.code_only else ("xorriso",))
    for tool in required:
        if not shutil.which(tool):
            raise RuntimeError("missing tool: " + tool)
    OUT.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / "build/base.lock.json").read_text())
    base = OUT / lock["image"]
    if not args.code_only and not base.exists():
        print("Downloading pinned Debian base", flush=True)
        urllib.request.urlretrieve(lock["url"], base)
    if not args.code_only and hashlib.file_digest(base.open("rb"), "sha512").hexdigest() != lock["sha512"]:
        raise RuntimeError("base checksum mismatch")
    disk = OUT / "ruxeonrx-1.0.qcow2"
    if args.code_only and (not args.refresh or not disk.exists()):
        raise ValueError("--code-only requires --refresh and an already-provisioned disk")
    if disk.exists() and not args.refresh:
        raise RuntimeError("disk exists; archive it before rebuilding (persistent user state is never overwritten)")
    if not disk.exists():
        run("qemu-img", "convert", "-O", "qcow2", str(base), str(disk))
        run("qemu-img", "resize", str(disk), "12G")
    key = OUT / "builder-key"
    if args.refresh and not key.exists():
        raise ValueError("refresh requires this development image's original builder-key")
    if not key.exists():
        run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
    pub = key.with_suffix(".pub").read_text().strip()
    seed_dir = OUT / "seed"
    seed_dir.mkdir(exist_ok=True)
    (seed_dir / "user-data").write_text("#cloud-config\ndisable_root: false\nssh_pwauth: false\nusers:\n  - name: root\n    ssh_authorized_keys:\n      - " + pub + "\n")
    (seed_dir / "meta-data").write_text("instance-id: ruxeonrx-builder\nlocal-hostname: ruxeonrx\n")
    seed = OUT / "seed.iso"
    if not args.code_only:
        run("xorriso", "-as", "mkisofs", "-quiet", "-V", "cidata", "-o", str(seed), str(seed_dir))
    else:
        previous = json.loads((OUT / "artifact.json").read_text())
        if previous["base"] != lock: raise ValueError("base lock changed; perform a full Linux rebuild")
    source = OUT / "source.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        for directory in ("build", "images", "packages", "services", "shell", "sdk", "tests", "tools", "docs"):
            for path in (ROOT / directory).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.add(path, arcname=str(path.relative_to(ROOT)))
    revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    qemu = ["qemu-system-x86_64", "-m", "2048", "-smp", "2", "-accel", args.accel,
            "-drive", f"file={disk},format=qcow2,if=virtio",
            "-nic", f"user,hostfwd=tcp:127.0.0.1:{args.port}-:22", "-display", "none", "-serial", "stdio", "-monitor", "none"]
    if not args.code_only: qemu += ["-cdrom", str(seed)]
    with (OUT / "builder.log").open("w") as log:
        process = subprocess.Popen(qemu, stdout=log, stderr=subprocess.STDOUT)
        try:
            ssh = wait_ssh(key, args.port, process)
            # Refresh boots the existing OS. Stop its desktop before replacing
            # session code; the builder's SSH/network connection remains live.
            run(*ssh, "if systemctl cat lightdm.service >/dev/null 2>&1; then systemctl stop lightdm.service; fi")
            run("scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-i", str(key), "-P", str(args.port), str(source), "root@127.0.0.1:/tmp/ruxeonrx-source.tar.gz")
            provision = ("RX_SKIP_APT=1 " if args.code_only else "") + "bash /opt/RuxeonRX/build/provision.sh " + revision + " " + lock["snapshot"]
            run(*ssh, "mkdir -p /opt/RuxeonRX && tar -xzf /tmp/ruxeonrx-source.tar.gz -C /opt/RuxeonRX && " + provision)
            run(*ssh, "sync; shutdown -h now")
            process.wait(timeout=90)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
    manifest = {"version": "1.0.0-beta", "revision": revision, "architecture": "x86_64", "base": lock,
                "disk_sha256": hashlib.file_digest(disk.open("rb"), "sha256").hexdigest()}
    (OUT / "artifact.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Built " + str(disk), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--accel", choices=("tcg", "kvm"), default="tcg")
    parser.add_argument("--port", type=int, default=2225)
    parser.add_argument("--refresh", action="store_true", help="update project files in the existing development image, preserving guest user data")
    parser.add_argument("--code-only", action="store_true", help="with --refresh, redeploy sources without changing the already-installed OS packages")
    args = parser.parse_args()
    build(args)
