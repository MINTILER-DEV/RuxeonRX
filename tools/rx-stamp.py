#!/usr/bin/env python3
"""Update the already-provisioned development guest's source revision."""
import json
from pathlib import Path
import re
import sys

revision = sys.argv[1]
if not re.fullmatch(r"[a-f0-9]{40}", revision):
    raise ValueError("expected a full git revision")
path = Path("/etc/ruxeonrx/build.json")
metadata = json.loads(path.read_text())
metadata["revision"] = revision
path.write_text(json.dumps(metadata, sort_keys=True) + "\n")
