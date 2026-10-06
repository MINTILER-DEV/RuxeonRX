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
        }

    @staticmethod
    def _virtualization() -> dict:
        kvm = Path("/dev/kvm")
        return {"kvm_present": kvm.exists(), "kvm_usable": os.access(kvm, os.R_OK | os.W_OK)}

    @staticmethod
    def _graphics() -> dict:
        cards = sorted(path.name for path in Path("/dev/dri").glob("card*")) if Path("/dev/dri").exists() else []
        return {"dri_cards": cards, "framebuffer_present": Path("/dev/fb0").exists()}
