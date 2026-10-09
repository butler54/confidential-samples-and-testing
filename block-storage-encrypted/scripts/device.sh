#!/bin/sh
# Helper routines never consider failed inspection proof of blank media.
normalize_device_types() {
  # LUKS2 has two headers; wipefs reports crypto_LUKS twice on the verified image.
  # Deduplicate identical signatures, but preserve conflicting types for rejection.
  printf '%s\n' "$1" | LC_ALL=C sort -u
}
device_type() {
  [ -b "$1" ] || return 1
  raw_types=$(timeout -k 2 30 wipefs --no-act --noheadings --output TYPE "$1") || return 1
  normalize_device_types "$raw_types"
}
blank_device() {
  # No signatures is necessary but insufficient: verify every byte is zero.
  signatures=$(device_type "$1") || return 1
  [ -z "$signatures" ] || return 1
  bytes=$(timeout -k 2 10 blockdev --getsize64 "$1") || return 1
  case "$bytes" in ''|*[!0-9]*|0) return 1 ;; esac
  timeout -k 2 120 cmp -n "$bytes" "$1" /dev/zero >/dev/null 2>&1
}
