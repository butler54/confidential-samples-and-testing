#!/bin/sh
set -eu
SCRIPTS_DIR=${SCRIPTS_DIR:-/opt/sample}
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
CONTROL_DIR=${CONTROL_DIR:-/run/sample}
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-900}
mkdir -p "$CONTROL_DIR"
if [ "${1:-}" = --prepare ]; then
  if [ "${SAMPLE_KIND:-plain}" != encrypted ]; then
    sh "$SCRIPTS_DIR/mount-storage.sh"
  fi
  sh "$SCRIPTS_DIR/storage-access.sh" --wait
  exit 0
fi
rm -f "$CONTROL_DIR/application.ready"
rm -f "$CONTROL_DIR/mount.expired"
# Report the deadline independently of a child stuck during cleanup/grace.
(
  sleep "$STARTUP_TIMEOUT" & sleeper=$!
  trap 'kill "$sleeper" 2>/dev/null || true; exit 0' HUP INT TERM
  wait "$sleeper"
  : > "$CONTROL_DIR/mount.expired"
  failure_event storage mount_timeout
) & reporter=$!
cancel_reporter() {
  kill "$reporter" 2>/dev/null || true
  wait "$reporter" 2>/dev/null || true
}
trap cancel_reporter EXIT
# One deadline covers mount preparation AND propagation/access, not two windows.
log_event storage_wait "path=$DATA_DIR" "timeout_seconds=$STARTUP_TIMEOUT"
if timeout -k 2 "$STARTUP_TIMEOUT" sh "$SCRIPTS_DIR/main.sh" --prepare; then
  cancel_reporter
  [ ! -f "$CONTROL_DIR/mount.expired" ] || exit 1
else
  status=$?
  cancel_reporter
  [ ! -f "$CONTROL_DIR/mount.expired" ] || exit 1
  case "$status" in 124|137) fail_startup storage mount_timeout ;; *) fail_startup storage preparation_failed ;; esac
fi
trap - EXIT
FILE_CHECK_STATE=started
if timeout -k 2 10 sh "$SCRIPTS_DIR/prose-file.sh"; then
  :
else
  status=$?
  case "$status" in 124|137) CREATED=unknown; fail_startup file file_check_timeout ;; *) exit "$status" ;; esac
fi
timeout -k 1 3 sh "$SCRIPTS_DIR/storage-access.sh" --fingerprint > "$CONTROL_DIR/application.ready.new" || fail_startup storage mount_lost
mv "$CONTROL_DIR/application.ready.new" "$CONTROL_DIR/application.ready"
if [ "${SAMPLE_KIND:-plain}" = nfs ]; then
  # Retain a signal supervisor only where a direct NFS mount needs best-effort cleanup.
  sleep infinity & child=$!
  cleanup() {
    rm -f "$CONTROL_DIR/application.ready"
    kill "$child" 2>/dev/null || true
    timeout -k 1 5 umount "$DATA_DIR" 2>/dev/null || true
  }
  trap 'cleanup; exit 0' HUP INT TERM
  wait "$child"
  cleanup
  exit 0
fi
# Exec ensures termination signals reach the foreground process directly.
exec sleep infinity
