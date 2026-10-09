#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
CONTROL_DIR=/run/sample
[ -s "$CONTROL_DIR/application.ready" ] || exit 1
current=$(timeout -k 1 3 sh "$SCRIPTS_DIR/storage-access.sh" --fingerprint) || exit 1
[ "$current" = "$(cat "$CONTROL_DIR/application.ready")" ] || exit 1
cd -P -- "${DATA_DIR:?}" || exit 1
pinned=$(timeout -k 1 1 stat -Lc '%d:%i' -- .) || exit 1
[ -f "${FILE_NAME:?}" ] && [ ! -L "$FILE_NAME" ] || exit 1
printf '%s\n' 'This file demonstrates persistent storage for this confidential container example.' | \
  timeout -k 1 1 cmp -s -- - "$FILE_NAME" || exit 1
# Reject an unmount/path swap or changed helper while checking prose.
[ "$current" = "$(timeout -k 1 3 sh "$SCRIPTS_DIR/storage-access.sh" --fingerprint)" ] || exit 1
[ "$pinned" = "$(timeout -k 1 1 stat -Lc '%d:%i' -- "$DATA_DIR")" ]
