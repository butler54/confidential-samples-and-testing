# Direct NFS mount

Mounts an operator-supplied NFS export **inside the main confidential container**, without a Kubernetes NFS volume, PV or PVC. After verifying the exact source/filesystem and main-container access, the entrypoint creates or verifies a stable release-specific public prose file. Pod replacement remounts the export and reads the same file. No server is provisioned and no HTTP Service/Route is needed.

## Prerequisites and boundaries

- OpenShift 4.22+ bare metal with Red Hat OSC 1.13, TDX/SEV-SNP and `kata-cc`; guest images and attestation/registry trust configured.
- Existing workload namespace, coco-pattern admission, and same-namespace `debug-initdata` containing `INITDATA`. `kbs-access` is normally propagated by the pattern; arbitrary namespaces need preparation.
- A reachable NFS server/export, compatible **guest-kernel** NFS support, TCP 2049 connectivity and suitable export permissions for the actual workload identity. Host NFS support alone is not proof of guest support.
- An explicitly authorized release ServiceAccount using an existing SCC permitting root/in-guest mounting. Optional namespace/account-only `security.sccBinding.create=true` creates a scoped use binding; default is false. No new SCC, cluster-wide binding, hostPath, host namespace or bidirectional propagation is used.

**Lab only:** debug policy permits exec; privileged root inside the Kata guest is required for this mount demonstration. Ordinary NFS does not encrypt transport or server-side data. Kerberos, NFS transport encryption, additional attested NFS credentials, server setup and root-squash reconfiguration are not implemented. Preserve server protections; use a specifically approved test export/identity, not a global no-root-squash workaround.

## Deploy and observe

Run from repository root:

```sh
export CTX=your-approved-test-context
export NS=kbs-access
helm install direct ./nfs-direct --kube-context "$CTX" -n "$NS" \
  --set-string nfs.server=nfs.example.internal --set-string nfs.exportPath=/exports/samples
oc --context "$CTX" -n "$NS" logs -l app.kubernetes.io/instance=direct -c application
```

Expected: `storage_wait`, `storage_accessible`, then `file_created` (`created=true, verified=true`). A replacement pod—or a reinstallation using the same identity/export—reports `file_existing_verified` (`created=false`) instead. The public sentence is `This file demonstrates persistent storage for this confidential container example.` followed by one newline. The generated filename incorporates full namespace/chart/release identity, so another release on the same export does not validate your file as its own.

Mounting and main-container access are supervised by one startup deadline (default 900 seconds), before file operations. A directory or helper marker cannot satisfy the gate; this chart needs no storage sidecar/shared PID namespace. Missing/mismatched source, unreadable/wrong file and failed creation produce explicit failure; no overwrite or temporary-root fallback is used. After verification a signal-aware foreground supervisor remains running and attempts bounded unmount on termination. Hard-mounted I/O can remain blocked in the kernel during server outages even when a supervisor reports timeout; restore connectivity/diagnose the guest rather than assuming user-space timeout guarantees kernel cancellation.

## Configuration

Complete defaults/comments and validation are local in `values.yaml` and `values.schema.json`.

| Value | Default / behavior |
|---|---|
| `nfs.server`, `nfs.exportPath` | Required existing hostname/IP and absolute export path; IPv6 sources are bracketed automatically. |
| `nfs.options` | `[vers=4.1, hard, proto=tcp]`; validated token list passed as data, never shell code. |
| `storage.mountPath` | `/mnt/storage`, normalized absolute main-container mount location. |
| `runtimeClassName` | `kata-cc`. |
| `initdata.mode`, `initdata.configMapName` | `configMap`, `debug-initdata`; referenced, never chart-owned. |
| `initdata.encoded` | With `mode=inline`, supplied gzip/base64 initdata wins over automatic injection. `clusterDefault` omits annotations and skips pattern injection. |
| `startup.timeoutSeconds`, `startup.pollSeconds` | `900`, `2`; does not bound node scheduling/image pulls. |
| `images.application` | Full tool-complete main-image override; the other common image roles do not create NFS containers. |
| `resources.application` | 2560Mi request/limit by default for a 2048Mi guest plus overhead; preserve compatible VM sizing. |
| `podLabels`, `podAnnotations`, `resourceLabels`, `resourceAnnotations` | Custom metadata cannot alter reserved identity/initdata/Helm ownership. |
| `serviceAccount.create`, `serviceAccount.name` | Generated isolated account; existing reference only with `create=false`. |
| `security.sccBinding.create`, `security.sccBinding.name` | Explicit scoped authorization opt-in and existing SCC reference. |

Block-storage size/class fields in the common defaults do not provision or affect NFS: there is no persistent-volume interface. Updating measured initdata requires its trusted-reference/policy updates and pod recreation as appropriate. A restrictive policy denying guest exec probes prevents Ready status; no policy is silently relaxed. `--logs-only` collects startup diagnostics, not full healthy mount verification.

## Images and disconnected deployment

Only `images.application` is consumed: `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1`, which supplies `mount.nfs` and mount/file verification tools. Other image keys exist only for configuration consistency. No custom image is needed, no image is built here, and no package installation runs at startup.

Mirror the tested artifact, override the full application reference, and provision guest registry CA/credentials/proxy plus disconnected attestation prerequisites. Node image-mirror configuration alone may not affect the guest. `tests/check-images.sh --image <mirror-reference>` verifies the role tool inventory, not guest-kernel or export connectivity. No encryption-key or attestation-status demonstration resource is fetched by this chart.

## Independent validation

```sh
python3 -m venv .venv
.venv/bin/python3 -m pip install -r nfs-direct/tests/requirements.txt
PATH="$PWD/.venv/bin:$PATH" sh nfs-direct/tests/run.sh
sh nfs-direct/tests/check-images.sh
sh nfs-direct/tests/check-prerequisites.sh --context "$CTX" --namespace "$NS" --release direct
sh nfs-direct/tests/verify-live.sh --context "$CTX" --namespace "$NS" --release direct --replace-pods --confirm-disposable
```

The offline runner supplies synthetic NFS inputs for render tests, creates no mount, and contacts no cluster. Live tools operate on the installed release with explicit context/namespace/release, validate main-container source and exact prose, and prove two new pod UIDs when replacements are requested. Use `--expect-existing` if your release's file was already retained. Use `--scc <name>` for a custom SCC. Negative-test conditions must be prepared separately on approved disposable exports/releases; `--expect-failure --failure-reason mount_timeout` observes the specific failure and no Ready status, without changing server data or manufacturing failures.

## Cleanup

```sh
helm uninstall direct --kube-context "$CTX" -n "$NS" --wait
# Or verify chart-owned cleanup explicitly:
sh nfs-direct/tests/verify-uninstall.sh --context "$CTX" --namespace "$NS" --release direct --confirm-destructive
```

All chart-owned objects are removed. The **external NFS server/export and its files remain**; the chart neither owns nor deletes them. The namespace, runtime, SCC, initdata, image credentials and platform Trustee configuration remain unowned. File cleanup on the external export is an operator decision, not an uninstall hook. Never use this example's cleanup to remove a shared server/export.

### Validation and safety additions

Cleanup captures actual Helm/controller-owned object identities and checks referenced external resources afterward; matching labels alone do not make a shared object release-owned. It uses one configured cleanup deadline. NFS has no backend asset adapter because the external export must remain intact.

Resource requests/limits must retain CPU and memory with coherent limits; main memory requests must be at least **2560Mi** for fixed guest RAM plus overhead. System mount targets and floating image aliases are rejected. Prose operations pin the verified filesystem view and work relative to it, so an intervening path/unmount change cannot redirect the write into the temporary root. Error logs distinguish full file/mount paths and state when the file check never ran.

The independent collection verifier checks an explicit cohort, all consumed admitted image references and selected initdata:

```sh
python3 nfs-direct/tests/live.py collection --context "$CTX" --namespace "$NS" --release direct \
  --cohort block-storage-plain:plain --cohort block-storage-encrypted:encrypted \
  --cohort nfs-direct:direct --cohort nfs-direct:other \
  --expected-mirror mirror.example:8443 --expected-initdata-mode configMap
```

Use your actual mirror expectation. `--removed-member nfs-direct:other` verifies absence and surviving members only after a separately approved removal; the verifier does not remove it. All tooling is packaged independently in this directory. No Python service is deployed; fully exec-denying policy compatibility remains a visible decision gate, not an implicitly weakened policy.
