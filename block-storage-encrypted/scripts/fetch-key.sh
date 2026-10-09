#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
# shellcheck source=key.sh
. "$SCRIPTS_DIR/key.sh"
CONTROL_DIR=/run/sample
DATA_DIR=$CONTROL_DIR
KBS_RESOURCE_PATH=${KBS_RESOURCE_PATH:?}
printf '%s' "$KBS_RESOURCE_PATH" | grep -Eq '^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$' || fail_startup key invalid_resource
umask 077
mkdir -p "$CONTROL_DIR"
chmod 700 "$CONTROL_DIR"
temp=$(mktemp "$CONTROL_DIR/key.XXXXXX")
trap 'rm -f "$temp"' EXIT
trap 'exit 1' HUP INT TERM
if ! http_status=$(curl --fail --silent --show-error --noproxy '*' --connect-timeout 5 --max-time 60 \
  --max-filesize 1024 --output "$temp" --write-out '%{http_code}' "http://127.0.0.1:8006/cdh/resource/$KBS_RESOURCE_PATH"); then
  fail_startup key key_denied
fi
[ "$http_status" = 200 ] || fail_startup key key_denied
validate_key_file "$temp" || fail_startup key key_empty_or_invalid
mv "$temp" "$CONTROL_DIR/key"
# Guest-memory-only key retained for native-helper restart; destroyed with the pod.
log_event key_available source=attested_cdh
