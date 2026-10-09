#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
# shellcheck source=device.sh
. "$SCRIPTS_DIR/device.sh"
DEVICE=/dev/block-device
DATA_DIR=$DEVICE
kind=$(device_type "$DEVICE") || fail_startup format inspection_failed
case "$kind" in
  xfs) log_event filesystem_reused "path=$DEVICE" ;;
  '')
    blank_device "$DEVICE" || fail_startup format nonblank_or_unreadable
    timeout -k 2 120 mkfs.xfs "$DEVICE" >/dev/null || fail_startup format format_failed
    log_event filesystem_created "path=$DEVICE"
    ;;
  *) fail_startup format incompatible_signature ;;
esac
