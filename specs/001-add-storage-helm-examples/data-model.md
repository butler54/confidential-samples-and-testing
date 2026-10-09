# Data Model: Confidential Storage Examples

This is a deployment/configuration model, not a database schema. See [values contract](contracts/values.md) and [runtime contract](contracts/runtime.md).

**Status**: Phase 1 design, assuming corrected upstream debug initdata as authorized by the user. See the [external trust prerequisite](research.md#r7--genuine-sealed-secret-mode-upstream-prerequisite).

## Example and Release

- `exampleId`: one of `block-storage-plain`, `block-storage-encrypted`, `nfs-direct`; immutable chart identity.
- `releaseName`, `namespace`: Helm deployment identity; one Deployment with exactly one replica and `Recreate` strategy per release.
- `resourcePrefix`: readable shortened example/release identity plus a hash of the full identity; resource suffixes derive from this prefix. No unrestricted full-name override.
- Owned objects: Deployment, ServiceAccount, scripts ConfigMap, optional namespaced SCC-use Role/RoleBinding, and, for block examples only, PVC. The sealed mode may own a Secret containing only a sealed envelope when supplied as values; referenced existing Secrets remain unowned.
- Relationships: a release selects one initdata configuration, one image reference per consumed role, one storage target, and one stable demonstration-file identity.
- Validation: namespace/release names follow Kubernetes/Helm rules; custom metadata cannot change reserved selectors, ownership, or generated initdata metadata. No Namespace, StorageClass, PV, SCC, operator, or Trustee resource is created.

## Initdata Selection

- `mode`: `configMap` (default), `inline`, or `clusterDefault`.
- `configMapName`: default `debug-initdata`; reference is in the release namespace.
- `encoded`: nonempty gzip/base64 initdata for inline mode; never a plaintext encryption key.
- Transitions: configuration changes affect replacement pods; externally updated ConfigMaps require a rollout restart because injection occurs at pod creation.
- Validation: one mode only; inline mode overrides admission injection; cluster-default mode explicitly omits the ConfigMap and inline annotations and suppresses pattern injection. Debug policy is a documented lab default, not production hardening.

## Block Storage Target

- `size`: default `1Gi`; `accessModes`: fixed `ReadWriteOnce`; `volumeMode`: fixed `Block`.
- `storageClass`: null means omit `storageClassName` so the cluster chooses its default; nonempty string chooses a specific class. Empty string is rejected rather than selecting no provisioner.
- `devicePath`: `/dev/block-device`; `filesystem`: XFS; chart-owned PVC name remains stable across pod replacements.
- States: `Unbound → Attached → Inspected → Initialized/Reused → Mounted → ApplicationAccessible`.
- Encrypted variant adds `KeyAvailable`, `LUKSInitialized/Reused`, and `Unlocked` before filesystem access. Unknown signatures and inspection failures are terminal errors, not proof of a blank disk.
- Lifecycle: pod replacement reuses the PVC and existing filesystem; Helm uninstall removes the PVC and lets the compatible CSI provider's `Delete` reclaim policy remove the PV/backend volume. Cleanup is incomplete until backend deletion is confirmed.

## NFS Storage Target

- `server`, `exportPath`: required nonempty operator inputs; optional version/security mount options are structured strings, never shell code.
- `mountPath`: default `/mnt/storage`; expected filesystem type/source must match the configured export.
- States: `Configured → Reachable → Mounted → ApplicationAccessible` or a bounded failure.
- External ownership: server, export, and files remain after uninstall; no Kubernetes NFS volume, PV, or PVC mediates access.
- Validation: absolute paths, no traversal/control characters, bounded option lengths; use quoted arguments without `eval`.

## Key-Delivery Selection (Encrypted Example Only)

- `mode`: `curl` (default), `sealed`, or `insecureSecret`; mutually exclusive single enum.
- `kbs.resourcePath`: default `default/kbsres1/key3`; exactly three validated resource segments.
- `sealed`: either a supplied genuine CoCo sealed envelope or an existing Secret reference, never both. The reference points to the same configured KBS resource.
- `sealedTrustPrerequisite`: corrected operator-provided debug initdata and supported guest-local public verification JWK matching the envelope `kid`. This is external infrastructure, not another KBS resource or a chart-owned configuration. Missing trust fails startup; an implicitly disabled signature verifier is not the accepted design.
- `insecureSecret`: existing Secret name/key, explicitly selected; no chart value accepts the plaintext key.
- Runtime key lifetime: confined to the confidential guest and needed helper process; memory-backed transient storage, no webroot, no shell tracing, no value/error-body logging.
- States: `Selected → Retrieved/Unsealed → NonemptyValidated → Used` or `Denied/Invalid → StartupFailed`. No mode downgrade.

## Demonstration File and Startup Result

- `filename`: generated from the full namespace/example/release identity; stable across replacement pods and distinct on shared NFS exports.
- `expectedProse`: fixed public sentence from the spec, encoded as UTF-8 with one terminal newline.
- `path`: intended storage root plus the generated filename; no path to an unrelated root filesystem is accepted.
- States: `Unchecked → StorageVerified → Absent → Created → ReadbackVerified` or `StorageVerified → Existing → ContentVerified`. Mismatch/access failures are terminal; existing content is never repaired automatically.
- File creation must not truncate a file that appeared concurrently; validate regular-file identity and avoid following file symlinks outside the intended storage.
- Result events: `storage_wait`, `storage_accessible`, `file_created`, `file_existing_verified`, or `startup_failed`, with path and explicit creation status. Only the known public prose may be logged.
- After successful file verification, the foreground application remains running. Readiness checks continued storage access; liveness must not mask storage failure or race the initial mount.
