#!/usr/bin/env python3
"""Run and test the complete desktop disk on Linux or Windows."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import importlib.util
spec = importlib.util.spec_from_file_location("image", ROOT / "tools/rx-image.py")
image = importlib.util.module_from_spec(spec); spec.loader.exec_module(image)


def command(args, disk, log):
    result = ["qemu-system-x86_64", "-accel", args.accel, "-m", "3072", "-smp", "2", "-drive", f"file={disk},format=qcow2,if=virtio", "-vga", "std", "-device", "ich9-intel-hda", "-device", "hda-duplex", "-audiodev", "none,id=audio0", "-nic", f"user,hostfwd=tcp:127.0.0.1:{args.port}-:22", "-serial", f"file:{log}", "-monitor", "none"]
    if args.test: result += ["-display", "none"]
    elif args.vnc: result += ["-display", "none", "-vnc", "127.0.0.1:1"]
    else: result += ["-display", "gtk"]
    if args.firmware: result += ["-bios", args.firmware]
    if args.safe: result += ["-fw_cfg", "name=opt/ruxeonrx/safe,string=1"]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disk", type=Path, default=ROOT / "out/desktop/ruxeonrx-1.0.qcow2")
    parser.add_argument("--accel", choices=("tcg", "kvm", "whpx"), default="tcg")
    parser.add_argument("--port", type=int, default=2225)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--vnc", action="store_true")
    parser.add_argument("--safe", action="store_true")
    parser.add_argument("--firmware")
    args = parser.parse_args()
    out = ROOT / "out/desktop"
    out.mkdir(parents=True, exist_ok=True)
    disk = args.disk.resolve()
    if not disk.is_file(): parser.error("desktop disk missing; build it using rx-image.py")
    if not args.test:
        raise SystemExit(subprocess.call(command(args, disk, out / "serial.log")))
    # Test in a disposable disk overlay: user's installed applications remain untouched.
    overlay = out / "acceptance.qcow2"
    if overlay.exists(): parser.error("acceptance overlay exists; archive it before rerunning")
    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", str(disk), str(overlay)], check=True)
    report = {"passed": False, "completed": [], "disk": str(disk), "disk_sha256": hashlib.file_digest(disk.open("rb"), "sha256").hexdigest(), "acceleration": args.accel}
    report_path = out / "acceptance.json"
    report_path.write_text(json.dumps(report, indent=2))
    key = out / "builder-key"
    requested_safe = args.safe
    for phase in ("initial", "resume", "safe"):
        args.safe = requested_safe or phase == "safe"
        with (out / (phase + "-qemu.log")).open("w") as log:
            vm = subprocess.Popen(command(args, overlay, out / (phase + "-serial.log")), stdout=log, stderr=subprocess.STDOUT)
            try:
                ssh = image.wait_ssh(key, args.port, vm)
                report["guest_build"] = json.loads(subprocess.check_output(ssh + ["cat /etc/ruxeonrx/build.json"], text=True))
                uid = subprocess.check_output(ssh + ["id -u rx"], text=True).strip()
                guest = f"runuser -u rx -- env DISPLAY=:0 XAUTHORITY=/home/rx/.Xauthority XDG_RUNTIME_DIR=/run/user/{uid} RX_RUNTIME=/run/user/{uid}/ruxeonrx python3 /opt/RuxeonRX/tests/e2e/guest_beta.py --phase {phase}"
                acceptance = subprocess.run(ssh + [guest])
                subprocess.run(["scp", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-i", str(key), "-P", str(args.port), "root@127.0.0.1:/home/rx/desktop-acceptance.png", str(out / (phase + "-desktop.png"))], check=True)
                if acceptance.returncode:
                    raise RuntimeError("graphical acceptance failed; screenshot and serial log preserved")
                subprocess.run(ssh + ["sync; shutdown -h now"], check=True)
                vm.wait(timeout=90)
            except Exception as error:
                report.update(failed_phase=phase, error=str(error))
                report_path.write_text(json.dumps(report, indent=2))
                raise
            finally:
                if vm.poll() is None: vm.terminate(); vm.wait(timeout=15)
        report["completed"].append(phase)
        report_path.write_text(json.dumps(report, indent=2))
    report["passed"] = True
    report_path.write_text(json.dumps(report, indent=2))
    print("RX 1.0 GNOME/taskbar/native desktop and recovery acceptance passed")


if __name__ == "__main__": main()
