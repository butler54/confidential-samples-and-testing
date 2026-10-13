# memory-security

Graduated memory-visibility and HTTP-vs-TLS buffer demonstrations for Red Hat confidential containers on bare-metal OpenShift. This example **supersedes the [butler54/coco-baremetal](https://github.com/butler54/coco-baremetal) test workflows** (its `BAREMETAL-tests.md`, `coco-testing` chart, and `get-*.sh` helpers), replacing its GitHub-hosted secret with a cluster-hosted endpoint so every step works where github.com is unreachable.

**DEMONSTRATION ONLY.** The endpoint route intentionally serves plaintext HTTP on port 80 alongside HTTPS on 443, and exactly one pod (`<release>-fetch-http`) fetches the magic string over HTTP. That plaintext exposure is the demonstration target of the transport comparison — it is confined to that pod, and HTTPS is the default for every other workload. Do not reuse this chart as a template for anything in production.

## What installs

| Object | Purpose |
|---|---|
| Deployment/Service/Route `<rel>-magic` | In-cluster web server (`ubi9/httpd-24`) serving `magic.txt` from a ConfigMap. Route terminates TLS at the edge and, by design, also answers HTTP. |
| Pod `<rel>-standard` | Ordinary container (`runc`). Fetches the string over HTTPS at startup; host-visible. |
| Pod `<rel>-kata` | Kata VM without memory encryption (`runtimeClassName: kata`). Host-first memory observation: string expected. |
| Pod `<rel>-coco` | Confidential VM (`runtimeClassName: kata-cc`, initdata-selected policy). Host-first memory observation: **string absent** thanks to TDX memory encryption. |
| Pods `<rel>-fetch-https` / `<rel>-fetch-http` | Transport comparison pair (kata-cc). One fetches over TLS, one over the chart's documented plaintext exception. |

Each fetcher pod downloads `https://<host>/magic.txt` (the HTTP one uses `http://`) at startup into an in-memory volume and sleeps, ready for observation. No automated tests exist: this README plus static chart linting are the validation, per repository policy.

## Prerequisites

A prepared cluster and tooling:

```bash
# Confidential and sandboxed runtime classes exist (coco-pattern installed)
oc get runtimeclass kata kata-cc

# The pattern's initdata ConfigMap is in your namespace (default: debug-initdata
# provided by the coco-pattern namespace propagation)
oc get configmap debug-initdata -n "$NAMESPACE"

# Hosts support memory encryption (run on a compute node)
oc debug node/NODE -- chroot /host grep -o tdx /proc/cpuinfo | head -1   # expect: tdx
```

You also need cluster-admin (`oc debug node` with privileged containers), `jq`, and:

- the **coredump helper image** (built in `butler54/containers`, consumed pinned as `quay.io/butler54/coredump:0.1.0`; used for host `gcore` dumps), and
- the Red Hat network tools image (`registry.redhat.io/openshift4/network-tools-rhel9:latest`) for packet capture.

Mutable image values for the chart itself: `images.demo`, `images.magicServer` (defaults are Red Hat UBI; any `registry.access.redhat.com/` prefix can be replaced by your mirror via `--set`).

## Install

Pick a route host on your cluster's apps domain (one command to discover the domain, then build the host):

```bash
APPS_DOMAIN=$(oc get ingresses.config/cluster -o jsonpath='{.spec.domain}')
HOST="memory-$NAMESPACE.$APPS_DOMAIN"

helm install memory ./memory-security --namespace "$NAMESPACE" --set route.host="$HOST"
```

Everything (endpoint, three tiers, and the fetch pair) installs in one release. Distinct releases coexist when each uses a distinct `route.host`. There is no upgrade flow — to reconfigure, uninstall and install again:

```bash
helm uninstall memory --namespace "$NAMESPACE"
```

Verify all five pods fetched the string:

```bash
for pod in memory-standard memory-kata memory-coco memory-fetch-https memory-fetch-http; do
  oc logs "$pod" -c fetch-key -n "$NAMESPACE" 2>/dev/null; oc get pod "$pod" -n "$NAMESPACE"
done
```

Fetch the cluster CA or keep `-k` as shown below — `-k` skips server verification **only**; the traffic is still encrypted, which is what the demonstrations measure.

## Observation 1 — graduated host visibility

### Tier 1: ordinary container — read it straight off the host

```bash
UID=$(sh memory-security/scripts/get-pod-uid.sh memory-standard "$NAMESPACE")
NODE=$(oc get pod memory-standard -n "$NAMESPACE" -o jsonpath='{.spec.nodeName}')
oc debug "node/$NODE" -- chroot /host cat "/var/lib/kubelet/pods/$UID/volumes/kubernetes.io~empty-dir/keys/magickey.txt"
```

**Expected**: `MyMagicKeyIsABanana` printed. Ordinary containers have no isolation from root on the host.

### Tier 2: sandboxed VM (`kata`) — the string survives a memory dump

```bash
MAC=$(sh memory-security/scripts/get-pod-mac.sh memory-kata "$NAMESPACE")
NODE=$(oc get pod memory-kata -n "$NAMESPACE" -o jsonpath='{.spec.nodeName}')
oc debug "node/$NODE"
# inside the debug pod:
chroot /host
podman run -it --privileged --pid=host quay.io/butler54/coredump:0.1.0 bash
PID=$(ps aux | grep qemu | grep -i "$MAC" | awk '{print $2}')
gcore "$PID"
strings "core.$PID" | grep -ci MyMagicKeyIsABanana
```

**Expected**: a positive count (typically ≥1). Kata's VM isolation is not memory encryption.

### Tier 3: confidential VM (`kata-cc`) — the dump finds nothing

```bash
MAC=$(sh memory-security/scripts/get-pod-mac.sh memory-coco "$NAMESPACE")
NODE=$(oc get pod memory-coco -n "$NAMESPACE" -o jsonpath='{.spec.nodeName}')
oc debug "node/$NODE"
# inside the debug pod:
chroot /host
podman run -it --privileged --pid=host quay.io/butler54/coredump:0.1.0 bash
PID=$(ps aux | grep qemu | grep -i "$MAC" | awk '{print $2}')
gcore "$PID"
strings "core.$PID" | grep -ci MyMagicKeyIsABanana
# Platform evidence that memory encryption is active:
grep -o tdx /proc/cpuinfo | head -1
```

**Expected**: count `0` for the string, `tdx` printed. **If you find the string**, the tier is not actually confidential — check the pod's runtime class and initdata before concluding anything about the platform.

## Observation 2 — HTTP leaves the string in buffers; TLS does not

The route serves both schemes by design (`insecureEdgeTerminationPolicy: Allow`) and exactly one pod, `memory-fetch-http`, uses plaintext. Everything else, including the identical-looking `memory-fetch-https`, uses TLS.

> **Secured-cluster prerequisite**: an ingress controller configured to reject or
> redirect plaintext (`insecureEdgeTerminationPolicy: Redirect` cluster policy or
> `ROUTE_CANONICAL` hardening) will break this demonstration — the HTTP fetch
> hangs or is upgraded, and you will see fetch-init container failures at install
> time. That failure is the symptom; the demo requires plaintext routes to be
> permitted. Uninstalling the release restores the secure posture.

> Freshness matters: trigger the fetch **immediately before** each observation, and compare against the expected outputs below before drawing conclusions.

### Router memory (ingress node)

```bash
# Fresh fetches, one per transport:
oc exec memory-fetch-http  -n "$NAMESPACE" -- curl -s  "http://$HOST/magic.txt"
oc exec memory-fetch-https -n "$NAMESPACE" -- curl -ks "https://$HOST/magic.txt"

ROUTER_NODE=$(oc -n openshift-ingress get pods -o wide \
  -l ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default \
  --no-headers | head -1 | awk '{print $7}')
oc debug "node/$ROUTER_NODE"
# inside the debug pod:
chroot /host
podman run -it --privileged --pid=host quay.io/butler54/coredump:0.1.0 bash
PID=$(ps aux | grep 'haproxy' | grep -v grep | awk '{print $2}' | head -1)
gcore "$PID"
strings "core.$PID" | grep -ci MyMagicKeyIsABanana
```

### Fetch pod's host node (network path)

```bash
POD_NODE=$(oc get pod memory-fetch-http -n "$NAMESPACE" -o jsonpath='{.spec.nodeName}')
# Watch port 80 traffic in one shell:
oc debug "node/$POD_NODE" --image=registry.redhat.io/openshift4/network-tools-rhel9:latest \
  -- tcpdump -i any -A 'tcp port 80'
# ...then re-fetch from another shell:
oc exec memory-fetch-http -n "$NAMESPACE" -- curl -s "http://$HOST/magic.txt"

# Control on TLS:
oc debug "node/$POD_NODE" --image=registry.redhat.io/openshift4/network-tools-rhel9:latest \
  -- tcpdump -i any -A 'tcp port 443'
oc exec memory-fetch-https -n "$NAMESPACE" -- curl -ks "https://$HOST/magic.txt"
```

### Expected outputs

| Observation | Subject | Expected |
|---|---|---|
| Host emptyDir read | `<rel>-standard` tier | **string printed** |
| QEMU memory dump | `<rel>-kata` tier | **string found (≥1)** |
| QEMU memory dump | `<rel>-coco` tier | **0 occurrences** (TDX-protected) |
| Router haproxy dump | after HTTP fetch | **string found** |
| Router haproxy dump | after TLS fetch | **string absent** |
| Host-node capture (port 80) | HTTP fetch | **plaintext string on the wire** |
| Host-node capture (port 443) | TLS fetch | **ciphertext only** |

"If the test was performed incorrectly" checklist: pod fetch logs missing, stale dump taken before the fresh fetch, the pod rescheduled to another node, or the cluster lacks TDX (`No CPU flag`) — verify each matches the fresh inputs above before interpreting a zero count.

**DEMONSTRATION ONLY reminder**: the HTTP path and the `Allow` route policy exist solely for this comparison. Deleting the release restores the secure default (`helm uninstall memory -n "$NAMESPACE"`).

## Cleanup

```bash
helm uninstall memory --namespace "$NAMESPACE"
```

The release owns every rendered object; nothing external (initdata ConfigMaps, registry Secrets, cluster policy) is touched. Lifecycle is delete-and-recreate only.

## Scope and validation

Static validation (`memory-security/tests/run.sh`: Helm lint, ShellCheck, syntax checks) proves chart shape only — it does not run pods, dumps, captures, or fetch anything, and no automated behavioural tests exist for this example. Observations above are the manual acceptance evidence.

The predecessor `coco-baremetal` repository is retired by parity with this chart; remaining gap: none of its content is required to run these tests.
