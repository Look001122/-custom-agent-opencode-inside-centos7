#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec env -u LD_LIBRARY_PATH -u LD_PRELOAD python3 "$ROOT/launch.py" "$ROOT" "$@"
