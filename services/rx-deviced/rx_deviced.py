"""Unprivileged hardware and runtime inventory for diagnostics."""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess


class DeviceInventory:
    def collect(self) -> dict:
        return {
            "architecture": platform.machine(),
            "kernel": platform.release(),
            "platform": platform.system(),
            "cpu_count": os.cpu_count() or 1,
            "virtualization": self._virtualization(),
            "graphics": self._graphics(),
            "network": self._names("/sys/class/net"),
            "audio": self._names("/sys/class/sound"),
            "bluetooth": self._names("/sys/class/bluetooth"),
            "storage": self._names("/sys/block"),
            "input": self._names("/sys/class/input"),
            "displays": self._names("/sys/class/drm"),
            "firmware_updates": {"status": "not-configured", "message": "The QEMU beta does not update host firmware; reported devices are guest-only."},
            "renderer": self._command(["glxinfo", "-B"]),
            "network_status": self._command(["nmcli", "-t", "device", "status"]),
            "audio_status": self._command(["wpctl", "status"]),
            "printer_status": self._command(["lpstat", "-p"]),
            "firmware_devices": self._command(["fwupdmgr", "get-devices", "--json"]),
            "graphics_drivers": {path.name: str((path / "device/driver").resolve()) for path in Path("/sys/class/drm").glob("card[0-9]") if (path / "device/driver").exists()},
        }

    @staticmethod
    def _command(command):
        if not shutil.which(command[0]): return {"status": "unavailable"}
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
            return {"status": "available" if result.returncode == 0 else "not-ready", "output": (result.stdout or result.stderr)[:16000]}
        except (OSError, subprocess.TimeoutExpired): return {"status": "not-ready"}

    @staticmethod
    def _names(directory):
        path = Path(directory)
        return sorted(item.name for item in path.iterdir()) if path.exists() else []

    @staticmethod
    def _virtualization() -> dict:
        kvm = Path("/dev/kvm")
        return {"kvm_present": kvm.exists(), "kvm_usable": os.access(kvm, os.R_OK | os.W_OK)}

    @staticmethod
    def _graphics() -> dict:
        cards = sorted(path.name for path in Path("/dev/dri").glob("card*")) if Path("/dev/dri").exists() else []
        return {"dri_cards": cards, "framebuffer_present": Path("/dev/fb0").exists()}
