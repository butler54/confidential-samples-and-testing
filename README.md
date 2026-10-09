# Confidential storage samples

Independent Helm examples for Red Hat OpenShift Sandboxed Containers 1.13 on bare-metal TDX/SEV-SNP. Each uses a Deployment, coco-pattern `debug-initdata` by default, and explicit startup logs proving the intended storage is accessible **before** creating or verifying a public prose file.

| Example | Demonstration |
|---|---|
| [block-storage-plain](block-storage-plain/README.md) | Attach a raw block claim, safely format blank media as XFS without encryption, and preserve data across pod replacement. |
| [block-storage-encrypted](block-storage-encrypted/README.md) | Initialize/reopen LUKS storage in the guest with attested curl, genuine CoCo sealed-token, or explicitly insecure Kubernetes Secret key delivery. |
| [nfs-direct](nfs-direct/README.md) | Mount an existing NFS export directly in the main container, without a Kubernetes NFS volume, PV or PVC. |

All examples have release-isolated names/selectors and stable distinct demonstration filenames. Install with distinct Helm release names to coexist in one namespace. Each directory contains all of its chart, scripts, tests and documentation; staged experimental samples are retained as reference, not runtime dependencies.

## Prepared environment

Use OpenShift 4.22+, a working `kata-cc` runtime, a workload namespace with propagated `debug-initdata`, appropriate guest registry/attestation trust, and explicitly authorized per-release service accounts. Block examples need raw-block CSI storage with backend **Delete** reclamation; NFS needs a reachable existing export and compatible guest-kernel support. See each example for complete prerequisites and narrowly scoped permissions.

**These are lab examples, not production security policies.** Debug exec access and privileged guest storage operations permit administrative inspection. Initdata and every consumed image reference are overridable, but restrictive policies must allow the operations/probes they are expected to support; charts never silently relax policies or bypass key-release authorization.

Sealed mode assumes corrected upstream debug initdata and supported guest-local signing trust, tracked in [coco-pattern #153](https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162). Filing that issue does not make the current upstream configuration compatible or prove sealed-mode live acceptance. Both attested key modes use one encryption-key resource; charts provision no additional Trustee resources.

## Observe persistence and cleanup

On a new volume: `storage_accessible` then `file_created` (`created=true`, `verified=true`). On a replacement pod: `file_existing_verified` (`created=false`). A wrong file, missing mount, invalid key or denied access reports failure instead of overwriting data or using the container's temporary filesystem.

- **Pod deletion:** the Deployment replaces it and reuses existing storage/data.
- **Helm uninstall of a block example:** deletes release-owned objects and claim; a compatible CSI provider deletes the backing volume, irreversibly destroying its data. Confirm actual backend deletion separately.
- **Helm uninstall of direct NFS:** deletes chart-owned resources, not the external server/export or its files.

Local tests use `sh <example>/tests/run.sh` with Helm and pinned Python/ShellCheck dependencies. They perform no cluster operations. Image checks and live replacement/uninstall verification are opt-in; live scripts require an explicit context/namespace/release and destructive confirmation, with provider-specific backend evidence for block deletion. No local image builds or startup package installations are used.
