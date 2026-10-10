#!/usr/bin/env python3
"""Export host build/acceptance evidence, never disks or SSH keys."""
import json
import os
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "out/desktop"
target = ROOT / "out/support.zip"
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("bundle.json", json.dumps({"format": 1, "kind": "desktop-build-evidence", "host": sys.platform}))
    for path in sorted(out.iterdir()) if out.exists() else []:
        if path.name not in {"artifact.json", "acceptance.json"} and path.suffix not in {".log", ".png"}:
            continue
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
            continue
        if path.suffix == ".png": archive.write(path, path.name)
        else:
            text = path.read_text(errors="replace")
            for private in (str(ROOT), str(Path.home()), os.environ.get("USERPROFILE", "")):
                if private: text = text.replace(private, "<path>")
            text = re.sub(r"(?i)(token|password|secret|api[_-]?key)(\s*[=:]\s*)[^\s\"']+", r"\1\2<redacted>", text)
            archive.writestr(path.name, text)
print(target)
