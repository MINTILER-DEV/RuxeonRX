"""Unprivileged hardware and runtime inventory for diagnostics."""
from __future__ import annotations

import os
from pathlib import Path
import platform


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
            "firmware_updates": {"status": "not-configured", "message": "QEMU alpha does not update host firmware."},
        }

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
