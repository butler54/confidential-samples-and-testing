#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
DATA_DIR=${DATA_DIR:?}
CONTROL_DIR=/run/sample
FILE_NAME=${FILE_NAME:?}
OP_TIMEOUT=5
CREATED=false
case "$FILE_NAME" in ''|*[!A-Za-z0-9_.-]*|.*) fail_startup file file_type_invalid ;; esac
timeout -k 2 "$OP_TIMEOUT" sh "$SCRIPTS_DIR/storage-access.sh" --check || fail_startup storage mount_source_mismatch
cd -P -- "$DATA_DIR" || fail_startup storage mount_source_mismatch
# CWD pins this filesystem. File operations below never re-resolve DATA_DIR.
check_view() {
  timeout -k 2 "$OP_TIMEOUT" sh "$SCRIPTS_DIR/storage-access.sh" --check || return 1
  pinned=$(stat -Lc '%d:%i' -- .) || return 1
  visible=$(stat -Lc '%d:%i' -- "$DATA_DIR") || return 1
  [ "$pinned" = "$visible" ]
}
check_view || fail_startup storage storage_view_changed
FILE_CHECK_STATE=started
prose='This file demonstrates persistent storage for this confidential container example.'
file=$FILE_NAME
umask 077
expected=$(mktemp "$CONTROL_DIR/expected.XXXXXX")
trap 'rm -f "$expected"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s\n' "$prose" > "$expected"
if [ -L "$file" ] || { [ -e "$file" ] && [ ! -f "$file" ]; }; then
  fail_startup file file_type_invalid
fi
existed=true
if [ ! -e "$file" ]; then
  # POSIX noclobber refuses a concurrent existing file/symlink; never truncate.
  if (set -C; printf '%s\n' "$prose" > "$file") 2>/dev/null; then
    CREATED=true
    existed=false
  else
    fail_startup file create_failed
  fi
fi
[ -f "$file" ] && [ ! -L "$file" ] || fail_startup file file_type_invalid
[ -r "$file" ] || fail_startup file read_failed
if timeout -k 2 "$OP_TIMEOUT" cmp -s -- "$expected" "$file"; then
  :
else
  status=$?
  if [ "$CREATED" = true ]; then fail_startup file readback_failed; fi
  case "$status" in 1) fail_startup file content_mismatch ;; *) fail_startup file read_failed ;; esac
fi
check_view || fail_startup storage storage_view_changed
if [ "$CREATED" = true ]; then event=file_created; else event=file_existing_verified; fi
log_event "$event" "path=$DATA_DIR/$file" "previously_existed=$existed" "created=$CREATED" verified=true "expected_prose=$prose"
