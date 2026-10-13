#!/bin/sh
# Static-only validation: Helm render + lint + python byte-compile. Never a live cluster.
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
command -v python3 >/dev/null
helm lint "$chart" --strict --kube-version 1.33.0 --set node.name=static.example.test --set pvc.storageClass=static-sc
shellcheck -x "$chart/tests/run.sh"
sh -n "$chart/tests/run.sh"
python3 -m py_compile "$chart/tools/bench.py"
# Constitution v2.0.0 IV: this repository defines/builds no containers.
if find "$chart" -iname 'Containerfile' -o -iname 'Dockerfile' | grep -q .; then
  echo "FAIL: container definition found in $chart" >&2
  exit 1
fi
