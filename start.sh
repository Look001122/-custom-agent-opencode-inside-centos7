#!/bin/bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
if [[ -z "${BAILIAN_BASE_URL:-}" ]]; then
  read -r -p 'Paste the Base URL from your Bailian console: ' BAILIAN_BASE_URL
fi
case "$BAILIAN_BASE_URL" in
  https://*/compatible-mode/v1) ;;
  *) echo 'Expected an HTTPS Base URL ending in /compatible-mode/v1.' >&2; exit 2 ;;
esac
if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
  read -r -s -p 'Bailian API Key (hidden): ' DASHSCOPE_API_KEY
  printf '\n'
fi
if [[ -z "$DASHSCOPE_API_KEY" ]]; then
  echo 'An API Key is required.' >&2
  exit 2
fi
export BAILIAN_BASE_URL DASHSCOPE_API_KEY
export OPENCODE_CONFIG="$ROOT/config/bailian.json"
exec "$ROOT/opencode" "$@"
