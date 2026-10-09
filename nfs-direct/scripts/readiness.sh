#!/bin/sh
set -eu
SCRIPTS_DIR=${SCRIPTS_DIR:-/opt/sample}
CONTROL_DIR=${CONTROL_DIR:-/run/sample}
[ -s "$CONTROL_DIR/application.ready" ] || exit 1
current=$(timeout -k 1 3 sh "$SCRIPTS_DIR/storage-access.sh" --fingerprint) || exit 1
[ "$current" = "$(cat "$CONTROL_DIR/application.ready")" ]
printf '%s\n' 'This file demonstrates persistent storage for this confidential container example.' | \
  timeout -k 1 1 cmp -s -- - "${DATA_DIR:?}/${FILE_NAME:?}"
