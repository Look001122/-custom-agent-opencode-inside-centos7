#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
NAME=xunchi-IC-agent-0.1.0-brand.3
if [ "$(id -u)" = 0 ]; then
  printf 'Use your normal EDA user, not root/su.\n' >&2
  exit 2
fi
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
  printf 'This package requires Linux x86_64.\n' >&2
  exit 2
fi
command -v python3 >/dev/null
command -v sha256sum >/dev/null
test -r "$ROOT/$NAME.tar.gz"
test -r "$ROOT/$NAME.tar.gz.sha256"
(cd "$ROOT" && sha256sum -c "$NAME.tar.gz.sha256")
mkdir -p "$HOME/.cache"
STAGE=$(mktemp -d "$HOME/.cache/xunchi-install.XXXXXXXX")
tar -xzf "$ROOT/$NAME.tar.gz" -C "$STAGE" --no-same-owner
python3 "$STAGE/$NAME/install.py"
