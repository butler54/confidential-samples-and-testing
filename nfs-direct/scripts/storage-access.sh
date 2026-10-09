#!/bin/sh
set -eu
SCRIPTS_DIR=${SCRIPTS_DIR:-/opt/sample}
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
DATA_DIR=${DATA_DIR:?}
CONTROL_DIR=${CONTROL_DIR:-/run/sample}
OP_TIMEOUT=${OP_TIMEOUT:-5}
PROC_ROOT=${PROC_ROOT:-/proc}

check_storage() {
  if [ "${SAMPLE_KIND:-plain}" = encrypted ]; then
    # State is published by the current helper only after a verified mount.
    [ -f "$CONTROL_DIR/helper.state" ] || return 1
    IFS=' ' read -r pid generation source extra < "$CONTROL_DIR/helper.state" || return 1
    case "$pid:$generation" in *[!0-9:]*|:*|*:) return 1 ;; esac
    [ -z "$extra" ] || return 1
    case "$source" in /dev/dm-[0-9]*|/dev/mapper/sample-*) ;; *) return 1 ;; esac
    kill -0 "$pid" 2>/dev/null || return 1
    actual=$(sed 's/.*) //' "$PROC_ROOT/$pid/stat" | awk '{print $20}') || return 1
    [ "$actual" = "$generation" ] || return 1
    # Both exact helper mount identity and main-container access are required.
    awk -v src="$source" '$5 == "/mnt/storage" { for(i=6;i<=NF;i++) if($i=="-" && $(i+1)=="xfs" && $(i+2)==src) ok=1 } END {exit !ok}' \
      "$PROC_ROOT/$pid/mountinfo" || return 1
    target="$PROC_ROOT/$pid/root/mnt/storage"
    if [ "${1:-}" = link ]; then
      mkdir -p "$(dirname "$DATA_DIR")"
      if [ -d "$DATA_DIR" ] && [ ! -L "$DATA_DIR" ]; then
        rmdir "$DATA_DIR" || return 1 # Never replace a nonempty directory.
      fi
      ln -sfn "$target" "$DATA_DIR" || return 1
    fi
    [ "$(readlink "$DATA_DIR")" = "$target" ] || return 1
  else
    source=${EXPECTED_SOURCE:?}
    info=$(timeout -k 2 "$OP_TIMEOUT" findmnt -rn -M "$DATA_DIR" -o SOURCE,FSTYPE) || return 1
    actual_source=${info% *}
    actual_type=${info##* }
    if [ "${SAMPLE_KIND:-plain}" = nfs ]; then
      [ "$actual_source" = "$source" ] || return 1
      case "$actual_type" in nfs|nfs4) ;; *) return 1 ;; esac
    else
      [ "$actual_type" = xfs ] || return 1
      [ "$(readlink -f "$actual_source")" = "$(readlink -f "$source")" ] || return 1
    fi
  fi
  timeout -k 2 "$OP_TIMEOUT" stat -- "$DATA_DIR/." >/dev/null 2>&1 || return 1
}

case "${1:---check}" in
  --check) check_storage ;;
  --fingerprint)
    check_storage
    if [ "${SAMPLE_KIND:-plain}" = encrypted ]; then
      cat "$CONTROL_DIR/helper.state"
    else
      timeout -k 2 "$OP_TIMEOUT" findmnt -rn -M "$DATA_DIR" -o SOURCE,FSTYPE
    fi
    ;;
  --wait)
    limit=${STARTUP_TIMEOUT:-900}
    poll=${POLL_SECONDS:-2}
    case "$limit:$poll" in *[!0-9:]*|0:*|*:0) fail_startup storage invalid_timeout ;; esac
    log_event storage_wait "path=$DATA_DIR" "timeout_seconds=$limit"
    end=$(($(date +%s) + limit))
    until check_storage link; do
      if [ "$(date +%s)" -ge "$end" ]; then
        log_event startup_failed stage=storage reason=mount_timeout "path=$DATA_DIR" created=false verified=false successful_condition=none file_check=not_run
        exit 1
      fi
      sleep "$poll"
    done
    log_event storage_accessible "path=$DATA_DIR" "source=$source" "filesystem=${actual_type:-xfs}"
    ;;
  *) exit 2 ;;
esac
