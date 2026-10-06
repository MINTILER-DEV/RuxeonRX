"""Launcher reads app records; it never scans desktop files or writes state."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "rx-appd"))
from rx_appd import AppRegistry


def search(state_dir: Path, query: str) -> list[dict]:
    return AppRegistry(state_dir).list(query)
