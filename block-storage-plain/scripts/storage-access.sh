#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
DATA_DIR=${DATA_DIR:?}
EXPECTED_SOURCE=${EXPECTED_SOURCE:?}

check_storage() {
  info=$(timeout -k 2 5 findmnt -rn -M "$DATA_DIR" -o SOURCE,FSTYPE) || return 1
  source=${info% *}
  [ "${info##* }" = xfs ] || return 1
  actual=$(readlink -f "$source") || return 1
  expected=$(readlink -f "$EXPECTED_SOURCE") || return 1
  [ -n "$actual" ] && [ "$actual" = "$expected" ] || return 1
  timeout -k 2 5 stat -- "$DATA_DIR/." >/dev/null 2>&1
}

case "${1:---check}" in
  --check) check_storage ;;
  --fingerprint) check_storage; printf '%s\n' "$info" ;;
  --wait)
    # main.sh bounds the entire mount/access preparation, not a second deadline.
    until check_storage; do sleep 2; done
    log_event storage_accessible "path=$DATA_DIR" "source=$source" filesystem=xfs
    ;;
  *) exit 2 ;;
esac
