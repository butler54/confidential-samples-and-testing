# kbs-client

Dirt-simple attestation key-broker client, delivered as its own minimal Helm chart — deliberately independent of the `memory-security` example. It runs one confidential container (kata-cc, TDX memory encryption) you can `oc exec` into and drive the key-broker client by hand against the cluster's Trustee. No automation, no behavioural tests: install, exec, retrieve, uninstall. Together with `memory-security`, this example completes the successor content for the retired `butler54/coco-baremetal` workflows.

## Prerequisites

```bash
# Confidential runtime class and initdata propagation (coco-pattern installed)
oc get runtimeclass kata-cc
NAMESPACE=kbs-demo   # pick your namespace
oc get configmap debug-initdata -n "$NAMESPACE"
```

The client image is built in `butler54/containers` and consumed pinned (`quay.io/butler54/kbs-client:0.1.0` placeholder — pin the published build before first use, or override via `--set images.client=...`). Attestation-enabled policies require the pattern's Trustee and a non-debug initdata policy for real secret release; the shipped default (`debug-initdata`) permits exec for exploration.

## Install

```bash
helm install kbs ./kbs-client --namespace "$NAMESPACE"
```

Everything is release-scoped; uninstall removes it cleanly:

```bash
helm uninstall kbs --namespace "$NAMESPACE"
```

## Find the Trustee address

The Trustee key broker is provided by the confidential-containers pattern, not this chart. Discover its route (adjust the name to your pattern version if it differs):

```bash
oc get routes -A | grep -i kbs
KBS="https://$(oc get route kbs-service -n trustee-operator-system -o jsonpath='{.spec.host}')"
```

To bake it into the pod environment at install time instead:

```bash
helm install kbs ./kbs-client --namespace "$NAMESPACE" --set kbs.address="$KBS"
```

## Retrieve a demonstration resource

Substitute the repository/type/tag of a resource you have released into Trustee. `default/repo-management/credential` is a placeholder for the pattern's demo path:

```bash
oc exec -it deploy/kbs-client -n "$NAMESPACE" -- \
  kbs-client --url "${KBS:-$KBS_ADDRESS}" get-resource --path default/repo-management/credential
```

**Expected**: the resource bytes on stdout — attestation succeeded and the broker released the secret. A non-confidential client (wrong runtime class, missing initdata, or a guest outside TDX) fails measurement verification and the retrieval is denied; that contrast is the point of the utility.

## Cleanup

```bash
helm uninstall kbs --namespace "$NAMESPACE"
```

## Scope and validation

Static validation (`kbs-client/tests/run.sh`: Helm lint/render assertions, ShellCheck) proves chart shape only. It does not contact Trustee, run the client, or pull images. The chart deploys independently of, and shares no state with, the `memory-security` example.
