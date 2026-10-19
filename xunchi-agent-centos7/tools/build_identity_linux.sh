#!/usr/bin/env bash
# Fresh pinned source with dependencies installed, Bun 1.3.14; no CentOS compiler needed.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  printf 'Usage: bash %s FRESH_UPSTREAM_SOURCE BUN_EXECUTABLE legacy|managed\n' "$0" >&2
  exit 2
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
SOURCE=$(CDPATH= cd -- "$1" && pwd -P)
BUN=$(realpath -- "$2")
MODE=$3
case "$MODE" in legacy|managed) ;; *) exit 2 ;; esac
test "$("$BUN" --version)" = 1.3.14
exec 9>"$SOURCE/.xunchi-build.lock"
flock -n 9 || { printf 'Source directory is already being built.\n' >&2; exit 2; }
test ! -e "$SOURCE/XUNCHI_IDENTITY_SOURCE.json" || { printf 'Use fresh pinned source for a reproducible build.\n' >&2; exit 2; }
python3 - "$SOURCE" <<'PY'
import json
from pathlib import Path
import sys
assert json.loads((Path(sys.argv[1]) / 'packages/opencode/package.json').read_text())['version'] == '1.19.0'
PY
for patch in 0002-xunchi-home-branding.patch 0003-select-musl-build.patch 0004-xunchi-terminal-identity.patch 0006-xunchi-product-identity.patch; do
  git -C "$SOURCE" apply --check "$ROOT/patches/$patch"
  git -C "$SOURCE" apply "$ROOT/patches/$patch"
done
if [ "$MODE" = managed ]; then
  git -C "$SOURCE" apply "$ROOT/patches/0005-xunchi-connections.patch"
fi
printf '{"product":"XunChi Agent","version":"0.1.1","mode":"%s"}\n' "$MODE" > "$SOURCE/XUNCHI_IDENTITY_SOURCE.json"
export PATH="$(dirname -- "$BUN"):$PATH"
export OPENCODE_VERSION=1.19.0 OPENCODE_CHANNEL=latest XUNCHI_BUILD_TARGET=linux-x64-musl
if [ -n "${MODELS_DEV_API_JSON:-}" ]; then
  test -r "$MODELS_DEV_API_JSON"
elif [ -r "$ROOT/vendor/models-api-20261016.json" ]; then
  export MODELS_DEV_API_JSON="$ROOT/vendor/models-api-20261016.json"
fi
unset OPENCODE_RELEASE OPENCODE_BUMP
cd "$SOURCE/packages/tui"
"$BUN" run typecheck
cd "$SOURCE/packages/opencode"
"$BUN" run typecheck
cd "$SOURCE"
"$BUN" run packages/opencode/script/build.ts --skip-install
readelf -l "$SOURCE/packages/opencode/dist/opencode-linux-x64-musl/bin/opencode" | grep 'ld-musl-x86_64.so.1'
