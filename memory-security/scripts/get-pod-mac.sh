#!/bin/sh
# Debugging tooling: print the primary OVN MAC of a demo pod, used to match its
# QEMU process on the host. User-invoked during the README walkthrough.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <pod-name> <namespace>" >&2
    exit 2
fi
command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }
mac=$(oc get pod "$1" -n "$2" -o json \
    | jq -r '.metadata.annotations["k8s.ovn.org/pod-networks"] | fromjson | .default.mac_address')
if [ -z "$mac" ] || [ "$mac" = "null" ]; then
    echo "error: no OVN MAC annotation on pod $1 in namespace $2" >&2
    exit 1
fi
printf '%s\n' "$mac"
