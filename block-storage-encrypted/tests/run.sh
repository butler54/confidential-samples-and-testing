#!/bin/sh
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
helm lint "$chart" --strict --kube-version 1.33.0
shellcheck -x -P "$chart/scripts" "$chart"/scripts/*.sh "$chart/tests/run.sh"
for script in "$chart"/scripts/*.sh "$chart/tests/run.sh"; do sh -n "$script"; done
python3 "$chart/tests/static.py"
