#!/bin/sh
# Log fields are escaped; never pass key material or arbitrary file contents here.
log_event() {
  printf 'event=%s' "$1"
  shift
  for field do
    escaped=$(printf '%s' "$field" | tr '\r\n' '  ' | sed 's/\\/\\\\/g; s/"/\\"/g')
    printf ' "%s"' "$escaped"
  done
  printf '\n'
}
failure_event() {
  failure_path=${DATA_DIR:-unknown}
  if [ "$1" = file ]; then failure_path="${DATA_DIR:-unknown}/${FILE_NAME:-unknown}"; fi
  check_state=not_run
  if [ "${FILE_CHECK_STATE:-not_run}" != not_run ]; then check_state=failed; fi
  log_event startup_failed "stage=$1" "reason=$2" "path=$failure_path" \
    "mount_path=${DATA_DIR:-unknown}" "file_path=${DATA_DIR:-unknown}/${FILE_NAME:-unknown}" \
    "file_check=$check_state" "timeout_seconds=${STARTUP_TIMEOUT:-0}" \
    "created=${CREATED:-false}" verified=false successful_condition=none
}
fail_startup() {
  failure_event "$@"
  exit 1
}
