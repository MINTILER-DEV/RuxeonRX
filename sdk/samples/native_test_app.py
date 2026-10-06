"""A portal-aware native sample; production apps use the future SDK binding."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "rx-portald"))
from rx_portald import Portal


def run(state_dir: Path, app_id: str) -> str:
    portal = Portal(state_dir)
    if not portal.allowed(app_id, "files"):
        return "file access denied"
    if not portal.allowed(app_id, "notifications"):
        return "notification permission denied"
    log_dir = state_dir / "diagnostics" / app_id
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "launch.log").write_text("native test app launched through portal\n")
    return "launched"
