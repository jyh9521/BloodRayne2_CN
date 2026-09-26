#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
script="$(cygpath -w "$here/rollback.ps1")"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script" "$@"
