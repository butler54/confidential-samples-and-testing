# Essential Values Contract

The values interface intentionally changes; only uninstall/reinstall is supported. Removed legacy keys must not be retained solely for compatibility. Values are configuration, not a channel for plaintext keys.

## Common inputs

| Path | Default | Purpose/constraint |
|---|---|---|
| `runtimeClassName` | `kata-cc` | Existing runtime class. |
| `initdata.configMapName` | `debug-initdata` | Existing same-namespace pattern ConfigMap; empty means cluster default when encoded data is absent. |
| `initdata.encoded` | empty | Explicit compressed/base64 initdata takes precedence over ConfigMap selection. Set skip-injection label for inline/cluster-default selection; never silently alter policy. |
| `images.storageHelper` | `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1` | Full reference used by every storage-tool/application container; mirror tag/digest allowed. |
| `imagePullPolicy` | `IfNotPresent` | Kubernetes policy. |
| `imagePullSecrets` | `[]` | Existing registry Secret references, not chart-owned. Guest registry trust remains an initdata prerequisite. |
| `startup.timeoutSeconds` | `900` | Integer 1–3600; poll interval is fixed at 2 seconds, with remaining-deadline checks. |
| `resources.application` | Existing CPU/memory requests/limits | Retain 2560Mi default request/limit for 2048Mi guest plus overhead; document sizing rather than parse quantities in templates. |
| `security.sccBinding.create` | `false` | Administrator opt-in only, scoped to this release's account. |
| `security.sccBinding.name` | `privileged` | Existing SCC for lab-required guest mounting; no namespace-wide grant. |

Every release creates its own account; no existing/default-account toggle. Fixed demonstration mount path `/mnt/storage`; no arbitrary metadata maps, mount-path settings or resource-name overrides. Values schemas list only relevant chart properties and reject unknown keys. No custom quantity language; use Kubernetes resource maps.

## Block inputs (plain and encrypted only)

| Path | Default | Purpose/constraint |
|---|---|---|
| `storage.size` | `1Gi` | Claim capacity. |
| `storage.storageClass` | `null` | Omit selection and use cluster default; explicit compatible class allowed. Empty string is not a supported class selection. |
| `resources.storageHelper` | Existing helper requests/limits | Actual formatter/native sidecar role only. |

Block/RWO claims belong to the release and have no keep policy; provisioner must support Block and Delete reclamation. NFS values contain none of these keys.

## Encrypted-only inputs

| Path | Default | Purpose/constraint |
|---|---|---|
| `images.utility` | `registry.access.redhat.com/ubi9/ubi:9.6` | Actual curl init container; full mirror override. |
| `resources.utility` | Existing utility requests/limits | Actual curl role. |
| `keyDelivery.mode` | `curl` | Enum: `curl`, `sealed`, `insecureSecret`. Exactly one active path; no fallback. |
| `keyDelivery.resourcePath` | `default/kbsres1/key3` | Three bounded safe resource segments; the single encryption-key resource. |
| `keyDelivery.secret.name` | empty | Existing Secret, required and nonempty for sealed/insecure; must be empty for curl. |
| `keyDelivery.secret.key` | `passphrase` | Referenced data key; choose `envelope` (or actual data key) for sealed tokens. |

No inline `sealed.envelope` option or chart-owned token Secret. The operator supplies genuine signed CoCo vault tokens identifying the configured resource. Sealed trust/signature verification occurs in the guest, not Helm. Secret references preserve ownership; no key/token contents appear in fixtures, NOTES or logs. The utility container is rendered only for curl; dormant encrypted alternate-mode settings are documented, not extra NFS/plain roles.

## NFS-only inputs

| Path | Default | Purpose/constraint |
|---|---|---|
| `nfs.server` | empty, required | Existing server DNS/IP; IPv6 gets bracketed in mount source. |
| `nfs.exportPath` | empty, required | Absolute export path. |
| `nfs.options` | `[vers=4.1, hard, proto=tcp]` | Validated list of mount options passed as one argument, never shell-evaluated. |

Only one application container. No block/PV/PVC, helper/utility images or resources, key delivery, NFS server provisioning or export deletion.

## Identity and metadata

- Base resource name is the full Helm release name. Suffixes `-scripts`, `-block`, `-scc`, `-sa` fit the 63-character limit with Helm's 53-character release limit; no truncation or name hash needed. The account always uses `-sa` so even a release named `default` cannot select/adopt the namespace's default account.
- Selectors use `app.kubernetes.io/name` (chart) and `app.kubernetes.io/instance` (release); fixed labels cannot be overridden by a metadata map.
- Prose basename contains chart, release and a short hash of namespace, keeping it readable and isolating namespaces sharing an export; it remains fixed across pod replacements, not across release deletion/recreation promises.
- Preserve required coco annotations/skip label, guest memory/create timeout and standard Helm labels directly. No new annotations, RBAC scope or admission mutation service.
