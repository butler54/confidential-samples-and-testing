# Direct in-container NFS

A small Helm example that mounts an existing NFS export directly in the confidential application container—no Kubernetes NFS volume, PV, PVC or storage sidecar.

## Follow the flow

1. [`scripts/main.sh`](scripts/main.sh) bounds the mount/access preparation.
2. [`scripts/mount-storage.sh`](scripts/mount-storage.sh) mounts the configured export at `/mnt/storage`; [`scripts/storage-access.sh`](scripts/storage-access.sh) verifies the actual source, NFS type and access.
3. [`scripts/prose-file.sh`](scripts/prose-file.sh) pins that storage view and creates/readbacks public prose only if absent, or verifies matching existing prose without rewriting it.
4. Readiness checks current storage and prose. Termination attempts a bounded unmount; it never deletes export data. The main foreground process simply holds the demonstration open.

## Prerequisites

- Use an existing prepared workload namespace; commands below use `examples` as its name, and server/export placeholders must be replaced.
- Prepared bare-metal TDX/SEV-SNP OpenShift/OSC confidential-container cluster with `kata-cc` (Kubernetes 1.33+ baseline).
- An existing writable NFS export reachable from the **guest**, supporting configured mount options and guest-kernel NFS. Host-side reachability alone is insufficient.
- Same-namespace coco-pattern `debug-initdata` or explicit initdata permitting guest mounts and supplied read-only exec probes. Fully exec-denying policies are unsupported; no silent policy relaxation.
- Red Hat image access/guest registry trust and an SCC allowing lab-only privileged in-guest mounting. Optional SCC use is administrator opt-in and account-scoped.

## Try it (on your disposable test environment)

```sh
helm install nfs ./nfs-direct --namespace examples \
  --set nfs.server=YOUR_SERVER --set nfs.exportPath=/YOUR_EXPORT
oc logs deployment/nfs -c application -n examples
```

Expect `event=file_created`, or `event=file_existing_verified` on later starts after replacing only the selected test pod. Failures emit `event=startup_failed` with a reason. Read-only exports, unreadable files and mismatched prose fail without rewriting existing data or reporting success on temporary storage. Hard-mount/file checks have deadlines; static validation cannot establish real kernel/network timeout behavior.

## Essential values

See the short, commented [`values.yaml`](values.yaml).

| Input | Use |
|---|---|
| `nfs.server`, `nfs.exportPath` | Required existing server DNS/IP and absolute export; unbracketed IPv6 server values are bracketed in mount source. |
| `nfs.options` | List of data arguments (default `vers=4.1,hard,proto=tcp`), never shell-evaluated. |
| `images.storageHelper`, `imagePullSecrets`, `imagePullPolicy` | One tool-complete application image/full mirror reference and existing pull credentials; no startup package downloads. |
| `initdata.encoded`, `initdata.configMapName` | Encoded compressed/base64 data wins; otherwise choose ConfigMap (`debug-initdata` default), or empty name for cluster default. |
| `runtimeClassName`, `startup.timeoutSeconds`, `resources.application` | Actual workload runtime, mount/access budget and resources; keep default 2560Mi for the 2048Mi guest plus overhead. |
| `security.sccBinding.create`, `.name` | Administrator opt-in to use one existing SCC for this release's account only. |

No block provisioning, key-delivery or unused container settings. Different release names coexist; prose filenames contain chart/release/namespace identity even on a shared export.

## Validate and clean up

Run `sh nfs-direct/tests/run.sh` from repository root with Helm, Python and dependencies from `tests/requirements.txt` available. Static lint/render/source/package checks use documentation-only NFS inputs; no server/cluster access or workload shell execution occurs. Static checks are not real NFS/persistence proof.

**Testing only: chart changes require uninstall and reinstall, not upgrades.** `helm uninstall nfs -n examples` removes the owned workload/account/config and optional bindings. The external NFS server, export and files are preserved, as are referenced initdata/pull resources. Reinstallation with the same identity may encounter its previous prose file; unexpected contents still fail closed.
