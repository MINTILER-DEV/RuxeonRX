#!/usr/bin/env bash
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"
python3 -m unittest discover -s tests/unit -v
./tools/rx-build build
RX_NO_KVM=1 ./tools/rx-build test
