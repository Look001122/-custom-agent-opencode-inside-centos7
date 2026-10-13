#!/bin/bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
printf 'OS / architecture / kernel:\n'
uname -srm
if command -v ldd >/dev/null 2>&1; then
  ldd --version | head -n 1
fi
if [[ -r /proc/cpuinfo ]]; then
  if grep -qwi avx2 /proc/cpuinfo; then
    printf 'AVX2: present\n'
  else
    printf 'AVX2: absent; this exact package has not been validated on this CPU.\n'
  fi
fi
printf '\nPackage integrity:\n'
(cd "$ROOT" && sha256sum -c SHA256SUMS)
printf '\nOpenCode version:\n'
"$ROOT/opencode" --version
printf '\nRoutes:\n'
ip route
printf '\nDNS configuration:\n'
cat /etc/resolv.conf
printf '\nThis command does not send an LLM request or print API keys.\n'
