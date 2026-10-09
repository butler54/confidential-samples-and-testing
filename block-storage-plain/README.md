# Plain block storage

A small Helm example for unencrypted XFS storage inside a confidential container.

## Follow the flow

1. [`templates/pvc.yaml`](templates/pvc.yaml) requests one raw Block/RWO claim.
2. [`scripts/format-storage.sh`](scripts/format-storage.sh) reuses XFS or formats confirmed zero-filled blank media. Inspection errors and other signatures fail closed.
3. [`scripts/main.sh`](scripts/main.sh) mounts the device in the application container and verifies source, XFS type and access before proceeding.
4. [`scripts/prose-file.sh`](scripts/prose-file.sh) pins that filesystem, creates/readbacks public prose only if absent, or verifies matching existing prose without rewriting it.
5. [`scripts/readiness.sh`](scripts/readiness.sh) checks both current storage and verified prose. No runtime service or custom image is needed.

## Prerequisites

- Use an existing prepared workload namespace; commands below use `examples` as its name.
- Prepared bare-metal TDX/SEV-SNP OpenShift/OSC confidential-container cluster with `kata-cc` (Kubernetes 1.33+ baseline).
- Same-namespace coco-pattern `debug-initdata`, or explicit initdata allowing guest mount operations and supplied read-only exec probes. Fully exec-denying policies are not supported; the chart does not relax policy.
- A CSI storage class supporting raw Block and **Delete** reclamation. Unspecified class uses the cluster default.
- Red Hat image access, guest registry trust, and an SCC allowing lab-only privileged in-guest mounting. An administrator may explicitly enable the narrowly account-scoped SCC binding.

## Try it (on your disposable test environment)

```sh
helm install plain ./block-storage-plain --namespace examples
oc logs deployment/plain -c application -n examples
```

Expected log outcomes: `event=file_created`, then `event=file_existing_verified` on later starts; failures emit `event=startup_failed` with a reason. Unexpected file contents are preserved, not printed or overwritten. The prose filename includes chart/release/namespace identity.

To demonstrate persistence, delete only the selected test pod: the Deployment recreates it using the same claim. Do not confuse this with uninstalling the release.

## Essential values

See the short, commented [`values.yaml`](values.yaml). Fixed paths (`/mnt/storage`, `/dev/block-device`) are part of the demonstration, not customization options.

| Input | Use |
|---|---|
| `storage.size`, `storage.storageClass` | Capacity and compatible class; default `1Gi`/cluster default. |
| `images.storageHelper`, `imagePullSecrets`, `imagePullPolicy` | Full mirror reference for both containers and existing pull credentials; no startup package downloads. |
| `initdata.encoded`, `initdata.configMapName` | Encoded compressed/base64 data wins; otherwise select ConfigMap (`debug-initdata` default), or set its name empty for cluster default. |
| `runtimeClassName`, `startup.timeoutSeconds` | Existing runtime and mount/access budget (900s default, 2s polling). |
| `resources.application`, `resources.storageHelper` | Actual container resources. Application needs guest RAM/overhead; keep at least the default 2560Mi for the 2048Mi guest. |
| `security.sccBinding.create`, `.name` | Opt-in `use` binding for this release's account and one existing SCC only. |

Different Helm release names can coexist; no arbitrary naming/metadata options or sibling chart dependencies.

## Validate and clean up

With Helm, Python and dependencies from `tests/requirements.txt` available, run `sh block-storage-plain/tests/run.sh` from repository root. It performs static lint/render/source/package checks only, never executes workload shell or accesses a cluster. Static success is not live persistence evidence.

**Testing only: chart changes require uninstall and reinstall, not upgrades.** `helm uninstall plain -n examples` deletes owned resources and the claim; a compatible provider's Delete policy reclaims the backing volume and its data. No deletion hook forces provider cleanup. External initdata/pull resources remain untouched. Pod replacement preserves data; release deletion does not.
