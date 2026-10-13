#!/bin/sh
# Static-only validation: Helm render commands and linting, never workload shell.
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
helm lint "$chart" --strict --kube-version 1.33.0
shellcheck -x "$chart/tests/run.sh"
sh -n "$chart/tests/run.sh"
