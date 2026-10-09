# Unencrypted block storage

Formats a chart-owned raw block volume as XFS only when it is confirmed blank, then mounts it directly in the main confidential container. On first start the application writes and verifies a public prose file; replacement pods verify the existing file without recreating it. **Storage is not encrypted at rest.**

## Target and prerequisites

- OpenShift 4.22+ bare metal with Red Hat OSC 1.13, `kata-cc`, Intel TDX or AMD SEV-SNP, and guest image pulling/attestation configured.
- An existing workload namespace with coco-pattern admission and a same-namespace `debug-initdata` ConfigMap containing nonempty `INITDATA`. The pattern normally propagates it to `kbs-access`; do not assume arbitrary namespaces inherit it.
- A CSI storage class supporting raw `Block`/`ReadWriteOnce` volumes and **Delete** reclaim policy with actual backend deletion support. Omit the class to use the cluster default; this chart does not create or alter storage classes.
- Administrator-approved permission for this release's ServiceAccount to use an existing SCC allowing the demonstrated in-guest mounts. The chart does not grant it automatically. `security.sccBinding.create=true` is an explicit opt-in to a namespace-only, account-specific binding; no SCC or cluster-wide binding is created.
- Registry authentication and trusted image/reference configuration inside the guest. Host/node pull configuration alone is not sufficient for all CoCo deployments.

These are **lab examples**, not production hardening. Main/storage containers run as privileged root **inside the Kata guest**, without hostPath or host namespace access. Debug initdata permits administrative exec and, together with privileged/shared-process access in the encrypted example, does not protect keys against such administrative inspection. Keep SELinux enforcing; do not globally relabel host `/dev` to work around driver errors.

## Deploy and observe

Run from the repository root with an explicitly selected prepared context/namespace:

```sh
export CTX=your-approved-test-context
export NS=kbs-access
helm install plain ./block-storage-plain --kube-context "$CTX" -n "$NS"
oc --context "$CTX" -n "$NS" logs -l app.kubernetes.io/instance=plain -c application
```

If an administrator has approved chart-managed scoped SCC-use authorization, add `--set security.sccBinding.create=true`; otherwise preauthorize the generated release account. See the rendered ServiceAccount name using `helm template` with **nonsecret** values. No namespace is created or owned.

Expected main-container events, in order:

1. `storage_wait`: waiting for the intended mount, not just a directory.
2. `storage_accessible`: source and filesystem verified from the main container.
3. `file_created` with `created=true, verified=true` on a new volume, or `file_existing_verified` with `created=false` after replacement.

The expected public sentence is `This file demonstrates persistent storage for this confidential container example.` with one final newline. The generated filename incorporates a hash of the full namespace/chart/release identity, remaining stable across replacement pods. Existing mismatched, unreadable, symlink/nonregular files are not overwritten. Failures log their stage/reason and do not start the foreground application. An interrupted first-time write or filesystem initialization may require operator diagnosis; the chart never repairs unknown data by force formatting.

The startup supervisor covers mounting and main-container access within `startup.timeoutSeconds` (900 by default). It does not promise a limit on node scheduling, image pulling, CSI attachment, or total cluster rollout time. Once verified, a foreground process keeps the container running; no HTTP server, Service or Route is required. Readiness checks storage and the expected prose rather than process existence alone.

## Configuration

All values are commented in `values.yaml` and validated by `values.schema.json`.

| Value | Default / behavior |
|---|---|
| `runtimeClassName` | `kata-cc`; choose only a supported confidential runtime. |
| `initdata.mode` | `configMap`; alternatives `inline` and `clusterDefault`. |
| `initdata.configMapName` | `debug-initdata`, referenced but never owned or modified. |
| `initdata.encoded` | Required in `inline` mode; supplied encoded value wins over admission injection. Store operator override files outside this chart. |
| `storage.mountPath` | `/mnt/storage`; normalized absolute path, not reserved runtime paths. |
| `storage.size` | `1Gi`; XFS requires sufficient capacity. |
| `storage.storageClass` | null omits the field and uses the default class; set a nonempty compatible class explicitly. Empty string is rejected. |
| `startup.timeoutSeconds`, `startup.pollSeconds` | `900`, `2`; finite startup mount gate. |
| `images.application`, `images.storageHelper`, `images.utility` | Full maintained image references; only consumed roles are rendered. |
| `resources.*` | Role-specific CPU/memory requests and limits. Main defaults reserve 2560Mi for a 2048Mi guest plus hypervisor overhead. |
| `podLabels`, `podAnnotations`, `resourceLabels`, `resourceAnnotations` | Additional metadata; reserved identity/initdata/Helm ownership fields cannot be overridden. |
| `serviceAccount.create`, `serviceAccount.name` | Dedicated generated account by default; an existing account reference only when creation is disabled. |
| `security.sccBinding.create`, `security.sccBinding.name` | `false`, `privileged`; operator-selected existing SCC and explicit scoped opt-in. |

For another initdata ConfigMap, set `initdata.configMapName`. Inline selection requires both `initdata.mode=inline` and `initdata.encoded`; cluster-default mode omits chart initdata annotations and opts out of pattern injection. Updating an external ConfigMap requires pod recreation and, where measured, corresponding Trustee reference/policy updates.

**Policy compatibility:** this chart's startup/readiness probes use guest exec. A restrictive override that denies those requests will prevent Ready status; the chart does not silently relax it. `--logs-only` below can collect startup diagnostics without interactive exec, but is not full mount/encryption/healthy-readiness acceptance.

## Image inventory and disconnected use

| Role | Default image | Tools |
|---|---|---|
| Main application / formatter | `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1` | Shell, timeout, mount/findmnt, blockdev/wipefs/XFS and public-file checks. |
| Utility (not consumed by this chart) | `registry.access.redhat.com/ubi9/ubi:9.6` | Common override contract only; no extra container is started. |

No images are built here and no packages are installed during startup. Mirror the tested artifacts and override every consumed `images.*` reference with full mirror references. Configure guest registry CA/credentials/proxy and disconnected attestation dependencies through the prepared environment/initdata; do not assume node IDMS/ITMS settings automatically apply inside the guest. Verify mirrored role tools with `tests/check-images.sh --image <mirror-reference>` before deployment. Plain storage performs no encryption-key or attestation-status resource fetch; pre-existing platform image/attestation policy remains an environment prerequisite.

## Independent validation

Local development validation (no cluster or image pull in the default runner):

```sh
python3 -m venv .venv
.venv/bin/python3 -m pip install -r block-storage-plain/tests/requirements.txt
PATH="$PWD/.venv/bin:$PATH" sh block-storage-plain/tests/run.sh
```

Opt-in image inventory check uses operator-configured registry authentication and network-disabled test containers:

```sh
sh block-storage-plain/tests/check-images.sh
```

Read-only prerequisite checking operates on an **installed release**. Approved live testing can then prove two replacements without changing the claim:

```sh
sh block-storage-plain/tests/check-prerequisites.sh --context "$CTX" --namespace "$NS" --release plain
sh block-storage-plain/tests/verify-live.sh --context "$CTX" --namespace "$NS" --release plain --replace-pods --confirm-disposable
```

The verifier checks new pod UIDs, admitted initdata, claim/PV identity, intended mount and exact prose. To inspect a replacement you created manually, use `--expect-existing`. Use `--scc <name>` for an approved custom SCC. Negative conditions must be prepared on separately approved disposable targets; `--expect-failure --failure-reason content_mismatch` observes the specific failure and requires the pod never become Ready during the observation window. It does not change data or keys to manufacture a failure.

## Cleanup — destructive for block storage

```sh
helm uninstall plain --kube-context "$CTX" -n "$NS" --wait
```

This deletes release-owned resources and its claim. A compatible CSI provider's `Delete` policy deletes the PV and backing volume asynchronously. **All data on that block volume is lost.** Pod deletion alone is different: the Deployment replaces the pod and reuses the claim/data.

Helm success or claim/PV disappearance alone is not backend-deletion evidence. On an approved disposable release, the stronger cleanup verifier requires an absolute executable provider-specific checker that accepts `(CSI driver, saved volume handle)` and returns zero **only when that backend asset is gone**:

```sh
sh block-storage-plain/tests/verify-uninstall.sh --context "$CTX" --namespace "$NS" --release plain --confirm-destructive --backend-check /absolute/path/to/provider-check
```

No backend checker is invented for an unknown storage provider. Missing evidence/timeouts fail verification. Never remove CSI finalizers or modify global reclaim policy as a cleanup shortcut. The namespace, runtime, SCC, storage class, initdata, pull credentials, Trustee and externally supplied resources remain unowned and untouched.

### Validation adapter and collection contract

The backend adapter returns **0** only for proven absence, **3** while the asset still exists, and another nonzero result for a terminal/checker error. Cleanup polls pending results within one deadline shared by Helm teardown, owned-object removal, PV removal and backend evidence. Matching application labels alone do not establish ownership; referenced external resource identity/content is checked after teardown.

Every resource role must retain CPU/memory requests and limits, with limits covering requests. Main memory requests must reserve at least **2560Mi** for fixed 2048Mi guest RAM and overhead. System mount targets such as `/usr` are rejected, as are floating aliases such as `nightly`.

Read-only collection checks require all three charts plus a second release explicitly, with no automatic discovery or removal:

```sh
python3 block-storage-plain/tests/live.py collection --context "$CTX" --namespace "$NS" --release plain \
  --cohort block-storage-plain:plain --cohort block-storage-encrypted:encrypted \
  --cohort nfs-direct:direct --cohort nfs-direct:other \
  --expected-mirror mirror.example:8443 --expected-initdata-mode configMap
```

Use `--removed-member nfs-direct:other` only after a separately approved removal; the check verifies the other members still have Ready pods and valid storage/prose. It does not remove the member. The mirror expectation checks every consumed admitted-pod image; specify your actual mirror or omit that flag for connected validation. Each chart includes its own copy of the verification tooling, not a sibling dependency.

Prose operations pin the validated filesystem view, work relative to it, and recheck the visible view before success logging. File errors identify the full filename; mount timeout reports the configured budget and `file_check=not_run`. A deadline reporter logs expiry independently of a stuck child's cleanup grace. None of these safeguards changes the agent policy: fully exec-denying overrides remain an unresolved compatibility gate, not successful logs-only validation.
