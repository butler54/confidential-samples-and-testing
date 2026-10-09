#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
CONTROL_DIR=/run/sample
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-900}
mkdir -p "$CONTROL_DIR"

# Mount and verify in the main container, under one preparation deadline.
if [ "${1:-}" = --prepare ]; then
  sh "$SCRIPTS_DIR/mount-storage.sh"
  sh "$SCRIPTS_DIR/storage-access.sh" --wait
  exit 0
fi
rm -f "$CONTROL_DIR/application.ready"
log_event storage_wait "path=$DATA_DIR" "timeout_seconds=$STARTUP_TIMEOUT"
if timeout -k 2 "$STARTUP_TIMEOUT" sh "$SCRIPTS_DIR/main.sh" --prepare; then
  :
else
  status=$?
  case "$status" in 124|137) fail_startup storage mount_timeout ;; *) fail_startup storage preparation_failed ;; esac
fi
FILE_CHECK_STATE=started
if timeout -k 2 10 sh "$SCRIPTS_DIR/prose-file.sh"; then
  :
else
  status=$?
  case "$status" in 124|137) CREATED=unknown; fail_startup file file_check_timeout ;; *) exit "$status" ;; esac
fi
timeout -k 1 3 sh "$SCRIPTS_DIR/storage-access.sh" --fingerprint > "$CONTROL_DIR/application.ready.new" || fail_startup storage mount_lost
mv "$CONTROL_DIR/application.ready.new" "$CONTROL_DIR/application.ready"

# Only NFS needs a foreground signal supervisor for best-effort unmount.
sleep infinity & child=$!
cleanup() {
  rm -f "$CONTROL_DIR/application.ready"
  kill "$child" 2>/dev/null || true
  timeout -k 1 5 umount "$DATA_DIR" 2>/dev/null || true
}
trap 'cleanup; exit 0' HUP INT TERM
wait "$child"
cleanup
