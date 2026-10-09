#!/bin/sh
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
helm lint "$chart" --strict --kube-version 1.33.0
shellcheck -x -P "$chart/scripts" "$chart"/scripts/*.sh "$chart"/tests/*.sh
scratch=$(mktemp -d "${TMPDIR:-/tmp}/coco-encrypted-tests.XXXXXX")
python3 -m pytest -q "$chart/tests" --basetemp "$scratch/pytest"
