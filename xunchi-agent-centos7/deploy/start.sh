#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
CONFIG=${OPENCODE_CONFIG:-"$HOME/opencode-bailian-v1.json"}
if [ ! -r "$CONFIG" ]; then
  printf 'OpenCode config not found: %s\nSet OPENCODE_CONFIG to your existing config.\n' "$CONFIG" >&2
  exit 2
fi
if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
  if [ ! -t 0 ]; then
    printf 'DASHSCOPE_API_KEY is missing. Start in an interactive terminal.\n' >&2
    exit 2
  fi
  read -r -s -p 'Bailian API Key: ' DASHSCOPE_API_KEY
  printf '\n'
fi
if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
  printf 'API Key must not be empty.\n' >&2
  exit 2
fi
export DASHSCOPE_API_KEY
export OPENCODE_CONFIG="$CONFIG"
if [ "${XUNCHI_TERMINAL_PROFILE:-legacy-vte}" = legacy-vte ] && [ -t 0 ] && [ -t 1 ]; then
  exec env -u LD_LIBRARY_PATH -u LD_PRELOAD python3 "$ROOT/terminal_compat.py" "$ROOT/opencode" "$@"
fi
exec "$ROOT/opencode" "$@"
