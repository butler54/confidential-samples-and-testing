#!/bin/sh
set -eu
DATA_DIR=${DATA_DIR:?}
EXPECTED_SOURCE=${EXPECTED_SOURCE:-/dev/block-device}
mkdir -p "$DATA_DIR"
if ! findmnt -rn -M "$DATA_DIR" >/dev/null; then
  mount -t xfs "$EXPECTED_SOURCE" "$DATA_DIR"
fi
sh "${SCRIPTS_DIR:-/opt/sample}/storage-access.sh" --check
