#!/bin/sh
set -eu
SCRIPTS_DIR=/opt/sample
# shellcheck source=log.sh
. "$SCRIPTS_DIR/log.sh"
DATA_DIR=${DATA_DIR:?}
EXPECTED_SOURCE=${EXPECTED_SOURCE:?}
NFS_OPTIONS=${NFS_OPTIONS:-vers=4.1,hard,proto=tcp}
# Values are structured/validated at render time and never interpreted as shell.
case "$EXPECTED_SOURCE" in *[!A-Za-z0-9_./:\[\]-]*) fail_startup storage invalid_nfs_source ;; esac
case "$NFS_OPTIONS" in ''|*[!A-Za-z0-9_,.=-]*) fail_startup storage invalid_nfs_options ;; esac
command -v mount.nfs >/dev/null || fail_startup storage missing_nfs_client
mkdir -p "$DATA_DIR"
if ! findmnt -rn -M "$DATA_DIR" >/dev/null; then
  mount -t nfs -o "$NFS_OPTIONS" "$EXPECTED_SOURCE" "$DATA_DIR" || fail_startup storage nfs_mount_failed
fi
sh "$SCRIPTS_DIR/storage-access.sh" --check || fail_startup storage mount_source_mismatch
