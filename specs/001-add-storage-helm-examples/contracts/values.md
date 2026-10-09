# Helm Values Contract

Each root-level example is an independent Helm v2 application chart, initial chart version `0.1.0`. Install directly from its directory. No chart dependencies or shared runtime files are required.

**Status**: Phase 1 contract, assuming externally corrected debug initdata and supported guest-local verification-key provisioning. See [upstream prerequisite](../research.md#r7--genuine-sealed-secret-mode-upstream-prerequisite); this does not claim current stock configuration works.

## Common Configuration

| Value | Default | Contract |
|---|---|---|
| `runtimeClassName` | `kata-cc` | Nonempty confidential runtime; overrides must be documented for the target. |
| `initdata.mode` | `configMap` | Enum: `configMap`, `inline`, `clusterDefault`. |
| `initdata.configMapName` | `debug-initdata` | Required only for ConfigMap selection; same namespace. |
| `initdata.encoded` | empty | Required for inline mode; exact encoded string is passed through. |
| `podLabels`, `podAnnotations` | empty maps | String maps; reserved identity/initdata fields are rejected if conflicting. |
| `resourceLabels`, `resourceAnnotations` | empty maps | String maps; cannot alter Helm ownership or release selection. |
| `images.application` | `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1` | Tool-complete main container; verify mount/prose then remain in a foreground process. Full image override must preserve required tools. |
| `images.storageHelper` | `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1` | Plain formatting init and encrypted native helper; direct NFS mounts in its main container and does not render this separate role. |
| `images.utility` | `registry.access.redhat.com/ubi9/ubi:9.6` | Curl retrieval only when needed; exact curl/validation-tool inventory and digest must be verified before merge. |
| `imagePullPolicy` | `IfNotPresent` | Kubernetes pull-policy enum. |
| `imagePullSecrets` | empty list | References to existing pull Secrets; guest trust/authentication remains an initdata prerequisite. |
| `storage.mountPath` | `/mnt/storage` | Absolute normalized path; no control characters or traversal. |
| `startup.timeoutSeconds` | `900` | Integer 1–3600; upper bound for the main-container mount gate, not a claim about total scheduling time. |
| `startup.pollSeconds` | `2` | Integer 1–30, not greater than the timeout. |
| `resources.application`, `resources.storageHelper`, `resources.utility` | documented role-specific requests/limits | Override independently; account for guest RAM and hypervisor overhead. |
| `serviceAccount.create` | `true` | Creates an isolated release-owned ServiceAccount with API token automount disabled. |
| `serviceAccount.name` | generated | Existing-account reference only when creation is disabled; operator must ensure isolation. |
| `security.sccBinding.create` | `false` | Optional namespaced Role/RoleBinding granting only `use` of the named existing SCC to this release account. |
| `security.sccBinding.name` | `privileged` | Existing SCC; permission to create its binding is an explicit administrator prerequisite. |

`replicas: 1` and Deployment `strategy.type: Recreate` are fixed. No host PID/network/IPC access, hostPath, NodePort, cluster-wide binding, namespace creation, or configurable arbitrary startup shell is exposed. Mount-related UID/capability exceptions must be explicit in chart documentation rather than claimed as restricted-pod compliance.

## Block Charts

| Value | Default | Contract |
|---|---|---|
| `storage.size` | `1Gi` | Positive Kubernetes quantity. |
| `storage.storageClass` | null | Omit `storageClassName`; nonempty string is an explicit class. Empty string is invalid. |

Volume mode, supported filesystem, device path, and access mode are fixed by the runtime contract. No existing-claim or retain-on-uninstall mode is included: claims are release-owned, and the selected class/provider must delete backing storage when the claim is deleted.

## Encrypted Chart

| Value | Default | Contract |
|---|---|---|
| `keyDelivery.mode` | `curl` | Single feature-selector enum: `curl`, `sealed`, `insecureSecret`; other combinations are rejected. |
| `keyDelivery.kbs.resourcePath` | `default/kbsres1/key3` | One KBS resource identifier; never the key contents. |
| `keyDelivery.sealed.existingSecret.name` | empty | Existing genuine CoCo sealed-envelope Secret. |
| `keyDelivery.sealed.existingSecret.key` | `envelope` | Secret field carrying a sealed envelope, not a bare KBS URI. |
| `keyDelivery.sealed.envelope` | empty | Optional operator-prepared sealed envelope only; if used, chart owns the envelope Secret. |
| `keyDelivery.insecureSecret.name` | empty | Required existing standard Secret in insecure mode. |
| `keyDelivery.insecureSecret.key` | `passphrase` | Required field; plaintext cannot be supplied through values. |

Require exactly one sealed source in sealed mode; reject conflicting sources and irrelevant active key-source fields. Failure never substitutes another mode. Attested modes reference the same resource, not two independent keys. See research for the exact sealed mechanism and utility requirements.

Sealed mode passes the genuine signed `sealed.` token through Secret-backed `PASS` environment data so Kata/CDH unseals it before the helper starts. The corrected guest trust configuration must supply the verification JWK matching its `kid` without an additional KBS resource. Charts never create that guest trust mechanism, change shared initdata, or expose a `skipVerification` fallback. A still-sealed token reaching the wrapper is rejected; legitimate unsealed plaintext is necessarily consumed inside the guest. The wrapper cannot prove the provenance of an improperly operator-supplied plaintext source, so source provisioning and positive/tampered-token tests are required before live acceptance. Passphrases use the shared 1–1024 printable-ASCII, no-newline/NUL, non-`sealed.`-prefix contract.

## NFS Chart

| Value | Default | Contract |
|---|---|---|
| `nfs.server` | empty | Required hostname/IP, no whitespace or shell metacharacters; IPv6 is bracketed when forming the mount source. |
| `nfs.exportPath` | empty | Required absolute export path; no traversal or control characters. |
| `nfs.options` | `["vers=4.1", "hard"]` | Validated list of mount-option tokens; no command interpretation. Site-specific overrides allowed. |

NFS transport encryption and Kerberos setup are not provided. `hard` mounts can block during server outages: bounded supervision of mount/read operations is required; a timeout is not permission to silently switch to unsafe storage.

## Rendered Interoperability

- ConfigMap mode: pod template has `coco.io/initdata-configmap: debug-initdata` (or selected name); no inline initdata or skip label.
- Inline mode: exact `io.katacontainers.config.hypervisor.cc_init_data` annotation; `coco.io/skip-initdata: "true"`; omit the ConfigMap selector.
- Cluster-default mode: omit both annotations; `coco.io/skip-initdata: "true"` prevents pattern injection, not the runtime's own global initdata.
- Referenced pattern ConfigMaps are not chart-owned or mutated. Charts create no initdata ConfigMaps by default, avoiding accidental ownership of synchronized pattern resources.
- Selectors include immutable chart identity and Helm release identity. Shortened names retain a hash of the full identity; suffix length is reserved before truncation.
- Values schema and template validation reject invalid modes, paths, reserved metadata conflicts, floating image references, and missing required inputs without consulting a live cluster. Live prerequisite validation separately checks ConfigMaps, Secrets, SCC access, and storage-class cleanup behavior.
