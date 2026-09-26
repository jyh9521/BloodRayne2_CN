#!/usr/bin/env bash
set -euo pipefail
target="${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
case "$target" in
  /*) ;;
  *) echo "ROLLBACK_ERROR target must be absolute" >&2; exit 2 ;;
esac
for name in scripted_other_speech.tsv engine_rayne_categories.tsv engine_rayne_samples.tsv source_hashes.json; do
  if [[ -f "$target/$name" ]]; then
    rm -- "$target/$name"
  fi
done
echo "ROLLBACK_OK inventory reports removed; game assets untouched"
