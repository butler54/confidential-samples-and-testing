#!/bin/sh
# Opt-in capability check only; never called by the offline test runner.
set -eu
role=storage
image=
platform=linux/amd64
while [ "$#" -gt 0 ]; do
  case "$1" in
    --role) role=${2:?--role requires storage or utility}; shift 2 ;;
    --image) image=${2:?--image requires a full image reference}; shift 2 ;;
    --platform) platform=${2:?--platform requires a platform}; shift 2 ;;
    *) printf 'Usage: %s [--role storage|utility] [--image reference] [--platform linux/amd64]\n' "$0" >&2; exit 2 ;;
  esac
done
case "$role" in
  storage) image=${image:-registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1} ;;
  utility) image=${image:-registry.access.redhat.com/ubi9/ubi:9.6} ;;
  *) printf 'Invalid role\n' >&2; exit 2 ;;
esac
case "$image" in -*) printf 'Invalid image reference\n' >&2; exit 2 ;; esac
command -v podman >/dev/null
podman pull --platform "$platform" "$image"
podman image inspect "$image" --format '{{.Digest}} {{.Architecture}}'
if [ "$role" = storage ]; then
  podman run --rm --network none --platform "$platform" --entrypoint /bin/sh "$image" -ec '
    for tool in sh timeout findmnt blkid blockdev wipefs mkfs.xfs cryptsetup mount umount stat cmp od head sleep readlink sort awk sed date mktemp; do
      command -v "$tool" >/dev/null || { printf "Missing tool: %s\n" "$tool" >&2; exit 1; }
    done
    printf "Encryption image tool inventory passed; this is not attestation/CSI validation.\n"
  '
else
  podman run --rm --network none --platform "$platform" --entrypoint /bin/sh "$image" -ec '
    for tool in sh curl timeout od wc tr head awk sed grep cat mv mktemp chmod rm; do
      command -v "$tool" >/dev/null || { printf "Missing tool: %s\n" "$tool" >&2; exit 1; }
    done
    printf "Retrieval image tool inventory passed; no key retrieval was attempted.\n"
  '
fi
