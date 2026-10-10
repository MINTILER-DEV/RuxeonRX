#!/usr/bin/env python3
"""Apply a QEMU safe-mode request before the graphical login starts."""
from pathlib import Path
import os
import pwd

flag = Path("/sys/firmware/qemu_fw_cfg/by_name/opt/ruxeonrx/safe/raw")
if flag.exists() and flag.read_bytes().startswith(b"1"):
    marker = Path("/home/rx/.local/state/ruxeonrx/safe-mode")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    user = pwd.getpwnam("rx")
    os.chown(marker, user.pw_uid, user.pw_gid)
