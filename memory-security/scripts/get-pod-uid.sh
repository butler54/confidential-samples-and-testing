#!/bin/sh
# Debugging tooling: print the UID of a demo pod, used to locate its emptyDir
# volume on the host filesystem. User-invoked during the README walkthrough.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <pod-name> <namespace>" >&2
    exit 2
fi
uid=$(oc get pod "$1" -n "$2" -o jsonpath='{.metadata.uid}')
if [ -z "$uid" ]; then
    echo "error: empty UID for pod $1 in namespace $2" >&2
    exit 1
fi
printf '%s\n' "$uid"
