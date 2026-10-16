#!/usr/bin/env bash
# Run in a modern Linux build environment, not on the CentOS 7 EDA machine.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  printf 'Usage: bash %s UPSTREAM_SOURCE_DIRECTORY BUN_EXECUTABLE\n' "$0" >&2
  exit 2
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
SOURCE=$(CDPATH= cd -- "$1" && pwd -P)
BUN=$(realpath -- "$2")
exec 9>"$SOURCE/.xunchi-build.lock"
flock -n 9 || { printf 'Another build is using this source directory.\n' >&2; exit 2; }
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
  printf 'Build requires a modern Linux x86_64 environment.\n' >&2
  exit 2
fi
if [ "$("$BUN" --version)" != 1.3.14 ]; then
  printf 'This pinned source requires the selected Bun 1.3.14 toolchain.\n' >&2
  exit 2
fi
export PATH="$(dirname -- "$BUN"):$PATH"
if [ -n "${XUNCHI_NODE_PREFIX:-}" ]; then
  test -f "$XUNCHI_NODE_PREFIX/include/node/node.h"
  export npm_config_nodedir="$XUNCHI_NODE_PREFIX"
fi
unset OPENCODE_RELEASE OPENCODE_BUMP
export OPENCODE_VERSION=1.19.0
export OPENCODE_CHANNEL=latest
export XUNCHI_BUILD_TARGET=linux-x64-musl
python3 "$ROOT/tools/prepare_branded_source.py" "$SOURCE"
cd "$SOURCE"
"$BUN" install --frozen-lockfile
cd "$SOURCE/packages/tui"
"$BUN" run typecheck
cd "$SOURCE"
# Frozen Linux install already includes these musl artifacts. Avoid the
# upstream all-OS/all-CPU reinstall when producing only this one target.
python3 - "$SOURCE" <<'PY'
from pathlib import Path
import sys
cache = Path(sys.argv[1]) / "node_modules/.bun"
patterns = (
    "@opentui+core-linux-x64-musl@*/node_modules/@opentui/core-linux-x64-musl/libopentui.so",
    "@parcel+watcher-linux-x64-musl@*/node_modules/@parcel/watcher-linux-x64-musl/watcher.node",
    "@ff-labs+fff-bin-linux-x64-musl@*/node_modules/@ff-labs/fff-bin-linux-x64-musl/libfff_c.so",
)
for pattern in patterns:
    if not any(path.is_file() and path.stat().st_size for path in cache.glob(pattern)):
        raise SystemExit("Required musl artifact is missing: " + pattern)
PY
"$BUN" run packages/opencode/script/build.ts --skip-install
ENGINE="$SOURCE/packages/opencode/dist/opencode-linux-x64-musl/bin/opencode"
test -s "$ENGINE"
readelf -l "$ENGINE" | grep 'ld-musl-x86_64.so.1'
printf 'BUILT_ENGINE=%s\n' "$ENGINE"
