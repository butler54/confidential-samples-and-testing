#!/bin/sh
# Opt-in capability check only; never called by the offline test runner.
set -eu
image=registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1
platform=linux/amd64
while [ "$#" -gt 0 ]; do
  case "$1" in
    --image) image=${2:?--image requires a full image reference}; shift 2 ;;
    --platform) platform=${2:?--platform requires a platform}; shift 2 ;;
    *) printf 'Usage: %s [--image reference] [--platform linux/amd64]\n' "$0" >&2; exit 2 ;;
  esac
done
case "$image" in -*) printf 'Invalid image reference\n' >&2; exit 2 ;; esac
command -v podman >/dev/null
podman pull --platform "$platform" "$image"
podman image inspect "$image" --format '{{.Digest}} {{.Architecture}}'
podman run --rm --network none --platform "$platform" --entrypoint /bin/sh "$image" -ec '
  for tool in sh timeout findmnt mount.nfs mount umount stat cmp od head sleep readlink awk sed date mktemp; do
    command -v "$tool" >/dev/null || { printf "Missing tool: %s\n" "$tool" >&2; exit 1; }
  done
  printf "NFS image tool inventory passed; guest kernel/export access remain unverified.\n"
'
