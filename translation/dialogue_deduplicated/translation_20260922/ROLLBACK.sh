#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
DEST="${1:-$HERE/../dialogue_unique.tsv}"
cp -- "$HERE/dialogue_unique.original.tsv" "$DEST"
cmp -s -- "$HERE/dialogue_unique.original.tsv" "$DEST"
printf '%s\n' 'ROLLBACK_OK original TSV bytes restored; translated=114 needs_review=125 pending=1465 blank=2'
