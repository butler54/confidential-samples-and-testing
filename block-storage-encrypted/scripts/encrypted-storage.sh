#!/bin/sh
set -eu
SCRIPTS_DIR=${SCRIPTS_DIR:-/opt/sample}
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
# shellcheck source=device.sh
. "$SCRIPTS_DIR/device.sh"
# shellcheck source=key.sh
. "$SCRIPTS_DIR/key.sh"
CONTROL_DIR=${CONTROL_DIR:-/run/sample}
DEVICE=${DEVICE:-/dev/block-device}
MAPPER_NAME=${MAPPER_NAME:-sample-storage}
DATA_DIR=/mnt/storage
PROC_ROOT=${PROC_ROOT:-/proc}
case "$MAPPER_NAME" in sample-*) ;; *) fail_startup encryption invalid_mapper ;; esac
case "$MAPPER_NAME" in *[!A-Za-z0-9_-]*) fail_startup encryption invalid_mapper ;; esac
mapper="/dev/mapper/$MAPPER_NAME"
child=
mapper_owned=false
mounted_owned=false
cleanup() {
  [ -z "$child" ] || kill "$child" 2>/dev/null || true
  if [ -f "$CONTROL_DIR/helper.state" ] && [ "$(awk '{print $1}' "$CONTROL_DIR/helper.state")" = "$$" ]; then
    rm -f "$CONTROL_DIR/helper.state"
  fi
  if [ "$mounted_owned" = true ]; then
    timeout -k 1 5 umount "$DATA_DIR" 2>/dev/null || true
    mounted_owned=false
  fi
  if [ "$mapper_owned" = true ]; then
    timeout -k 1 5 cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
    mapper_owned=false
  fi
}
# Install cleanup before opening anything or publishing state; termination can race publication.
trap 'cleanup; trap - EXIT; exit 0' HUP INT TERM
trap cleanup EXIT
umask 077
mkdir -p "$CONTROL_DIR"
chmod 700 "$CONTROL_DIR"
rm -f "$CONTROL_DIR/helper.state"
case "${KEY_MODE:-curl}" in
  curl)
    validate_key_file "$CONTROL_DIR/key" || fail_startup key key_empty_or_invalid
    key=$(cat "$CONTROL_DIR/key")
    ;;
  sealed|insecureSecret)
    key=${PASS:-}
    unset PASS # Prevent inheritance by cryptsetup/other child processes.
    case "$key" in sealed.*) fail_startup key unprocessed_sealed_token ;; esac
    temp=$(mktemp "$CONTROL_DIR/env-key.XXXXXX")
    printf '%s' "$key" > "$temp"
    if ! validate_key_file "$temp"; then
      rm -f "$temp"
      fail_startup key key_empty_or_invalid
    fi
    rm -f "$temp"
    ;;
  *) fail_startup key invalid_mode ;;
esac
kind=$(device_type "$DEVICE") || fail_startup encryption inspection_failed
fresh=false
case "$kind" in
  crypto_LUKS) ;;
  '')
    blank_device "$DEVICE" || fail_startup encryption nonblank_or_unreadable
    printf '%s' "$key" | timeout -k 2 120 cryptsetup luksFormat --type luks2 --pbkdf argon2id --pbkdf-memory 65536 --batch-mode --key-file - "$DEVICE" >/dev/null || fail_startup encryption format_failed
    fresh=true
    ;;
  *) fail_startup encryption incompatible_signature ;;
esac
# Test the key even when a mapper is already open; never reuse it to mask a wrong key.
printf '%s' "$key" | timeout -k 2 60 cryptsetup open --test-passphrase --key-file - "$DEVICE" >/dev/null || fail_startup encryption unlock_failed
if status=$(cryptsetup status "$MAPPER_NAME" 2>/dev/null); then
  backing=$(printf '%s\n' "$status" | awk '$1 == "device:" {print $2}')
  [ -n "$backing" ] || fail_startup encryption mapper_source_mismatch
  backing_real=$(readlink -f "$backing") || fail_startup encryption mapper_source_mismatch
  device_real=$(readlink -f "$DEVICE") || fail_startup encryption mapper_source_mismatch
  [ -n "$backing_real" ] && [ "$backing_real" = "$device_real" ] || fail_startup encryption mapper_source_mismatch
else
  printf '%s' "$key" | timeout -k 2 60 cryptsetup open --key-file - "$DEVICE" "$MAPPER_NAME" >/dev/null || fail_startup encryption unlock_failed
fi
mapper_owned=true
unset key
fs=$(device_type "$mapper") || fail_startup encryption inspection_failed
case "$fs" in
  xfs) ;;
  '')
    if [ "$fresh" != true ]; then
      blank_device "$mapper" || fail_startup encryption unrecognized_existing_data
    fi
    timeout -k 2 120 mkfs.xfs "$mapper" >/dev/null || fail_startup encryption filesystem_failed
    ;;
  *) fail_startup encryption incompatible_filesystem ;;
esac
mkdir -p "$DATA_DIR"
if ! findmnt -rn -M "$DATA_DIR" >/dev/null; then
  timeout -k 2 30 mount -t xfs "$mapper" "$DATA_DIR" || fail_startup encryption mount_failed
  mounted_owned=true
fi
source=$(readlink -f "$mapper")
mounted=$(findmnt -rn -M "$DATA_DIR" -o SOURCE,FSTYPE) || fail_startup encryption mount_failed
actual_source=${mounted% *}
[ "$(readlink -f "$actual_source")" = "$source" ] && [ "${mounted##* }" = xfs ] || fail_startup encryption mount_source_mismatch
mounted_owned=true
generation=$(sed 's/.*) //' "$PROC_ROOT/$$/stat" | awk '{print $20}')
printf '%s %s %s\n' "$$" "$generation" "$actual_source" > "$CONTROL_DIR/helper.state.new"
mv "$CONTROL_DIR/helper.state.new" "$CONTROL_DIR/helper.state"
log_event encrypted_storage_mounted "path=$DATA_DIR"
while :; do sleep 3600 & child=$!; wait "$child"; done
