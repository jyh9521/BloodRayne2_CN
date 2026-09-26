#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$HERE/rollback.ps1")" "$@"
