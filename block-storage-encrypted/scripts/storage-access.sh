#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
DATA_DIR=${DATA_DIR:?}
CONTROL_DIR=/run/sample

check_storage() {
  # The native helper publishes PID + start generation + source after mounting.
  [ -f "$CONTROL_DIR/helper.state" ] || return 1
  IFS=' ' read -r pid generation source extra < "$CONTROL_DIR/helper.state" || return 1
  case "$pid:$generation" in *[!0-9:]*|:*|*:) return 1 ;; esac
  [ -z "$extra" ] || return 1
  case "$source" in /dev/dm-[0-9]*|/dev/mapper/sample-*) ;; *) return 1 ;; esac
  kill -0 "$pid" 2>/dev/null || return 1
  actual=$(sed 's/.*) //' "/proc/$pid/stat" | awk '{print $20}') || return 1
  [ "$actual" = "$generation" ] || return 1
  # Shared PID namespaces do not share mounts. Verify the helper's exact mount.
  awk -v src="$source" '$5 == "/mnt/storage" { for(i=6;i<=NF;i++) if($i=="-" && $(i+1)=="xfs" && $(i+2)==src) ok=1 } END {exit !ok}' \
    "/proc/$pid/mountinfo" || return 1
  target="/proc/$pid/root/mnt/storage"
  if [ "${1:-}" = link ]; then
    mkdir -p "$(dirname "$DATA_DIR")"
    if [ -d "$DATA_DIR" ] && [ ! -L "$DATA_DIR" ]; then
      rmdir "$DATA_DIR" || return 1 # Never replace a nonempty directory.
    fi
    ln -sfn "$target" "$DATA_DIR" || return 1
  fi
  [ "$(readlink "$DATA_DIR")" = "$target" ] || return 1
  timeout -k 2 5 stat -- "$DATA_DIR/." >/dev/null 2>&1
}

case "${1:---check}" in
  --check) check_storage ;;
  --fingerprint) check_storage; printf '%s %s %s\n' "$pid" "$generation" "$source" ;;
  --wait)
    # main.sh bounds waiting/linking within the one preparation deadline.
    until check_storage link; do sleep 2; done
    log_event storage_accessible "path=$DATA_DIR" "source=$source" filesystem=xfs
    ;;
  *) exit 2 ;;
esac
