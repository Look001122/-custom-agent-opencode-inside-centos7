#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
NAME=xunchi-agent-0.1.1-identity.1
if [ "$(id -u)" = 0 ]; then
  printf 'Run as your normal EDA user, without su/sudo.\n' >&2
  exit 2
fi
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
  printf 'This upgrade requires Linux x86_64.\n' >&2
  exit 2
fi
(cd "$ROOT" && sha256sum -c "$NAME.tar.gz.sha256")
mkdir -p "$HOME/.cache"
STAGE=$(mktemp -d "$HOME/.cache/xunchi-identity.XXXXXXXX")
tar -xzf "$ROOT/$NAME.tar.gz" -C "$STAGE" --no-same-owner
python3 "$STAGE/$NAME/install_identity.py" "$@"
