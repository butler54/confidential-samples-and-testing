#!/bin/sh
# Static-only validation: Helm render commands and linting, never workload shell.
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
helm lint "$chart" --strict --kube-version 1.33.0 --set route.host=static.apps.example.test
shellcheck -x "$chart"/scripts/*.sh "$chart/tests/run.sh"
for script in "$chart"/scripts/*.sh "$chart/tests/run.sh"; do sh -n "$script"; done
