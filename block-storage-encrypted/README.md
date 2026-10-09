# Encrypted block storage

A single-replica Deployment provisions a raw block claim, safely initializes/reopens LUKS2 and XFS inside the confidential guest, and exposes its filesystem to the main container. After verified storage access, the main entrypoint creates or verifies the same public prose file on every pod start. No HTTP server, Service or Route is needed.

## Prerequisites and security boundary

- OpenShift 4.22+ bare metal, Red Hat OSC 1.13, Trustee 1.2, TDX/SEV-SNP and the `kata-cc` runtime; guest images, attestation trust and platform registry/image policy already configured.
- An existing workload namespace, coco-pattern admission and same-namespace `debug-initdata` containing `INITDATA`. The pattern commonly propagates it to `kbs-access`; other namespaces require explicit operator preparation.
- Raw-block CSI provisioning with `ReadWriteOnce`, sufficient capacity (default `1Gi`), and actual **Delete** reclamation. The chart does not create/change storage classes or provision Trustee.
- Exactly one preconfigured encryption-key resource, default identifier `default/kbsres1/key3`, with authorization for this workload. This example accepts **1–1024 printable ASCII bytes without a newline/NUL** as a passphrase; binary keys are not supported by its environment-based sealed transport. The two attested modes refer to that same resource; existing platform registry/image-policy prerequisites are not extra demonstration-key resources.
- Passphrases must not start with `sealed.`, which is reserved by Kata's environment-unsealing protocol; the same byte/prefix contract is applied in every mode.
- Per-release ServiceAccount permission to use an existing SCC permitting root/privileged mounting in the Kata guest. Optional `security.sccBinding.create=true` creates only a namespace/account-scoped use binding; default is false. No hostPath/host namespace or cluster-wide binding is created.

**Lab only:** default debug policy permits exec. Privileged shared-process containers and guest-memory key storage permit administrator/process inspection; this is not production key isolation. Keys are not logged, passed in expanded executable arguments, served, or embedded as plaintext values. `PASS` is unset before child processes to prevent further environment inheritance; this is not a claim of secure zeroization. No global host SELinux/device relabeling or package installation is performed.

## Deploy the default curl mode

```sh
export CTX=your-approved-test-context
export NS=kbs-access
helm install encrypted ./block-storage-encrypted --kube-context "$CTX" -n "$NS"
oc --context "$CTX" -n "$NS" logs -l app.kubernetes.io/instance=encrypted -c application
```

Default curl mode calls the supported guest-local `http://127.0.0.1:8006/cdh/resource/<repository>/<type>/<tag>` interface. CDH performs Trustee attestation/authorization; this is not anonymous direct KBS access. The fetch has bounded timeouts, loopback proxy bypass, HTTP/byte validation, and private memory-backed staging. The guest-memory key remains for native helper restarts and is destroyed with the pod; a replacement pod retrieves again. Denial/empty/invalid responses never fall back to another source.

The native helper uses a small chart-local state machine over Red Hat's cryptsetup/XFS utilities. The stock `luks-helper format-disk` binary is not invoked because its inspection-error formatting fallbacks do not meet this example's preservation requirements. Blank raw media must have no signatures and be entirely zero; probe errors or unknown/nonzero media are refused. Identical LUKS2 header signatures are deduplicated, conflicting signatures rejected. Existing encryption/XFS is reused, and the key is tested even when a mapper is already open. LUKS2 Argon2id memory is bounded to 64MiB to fit the helper's declared resources.

Shared PID namespace does **not** share mount namespaces. The helper publishes current PID/start generation and verified source only after mounting. The main entrypoint verifies that current helper mount and access through `/proc/<pid>/root/mnt/storage`, then establishes its application-visible path. No fixed PID, postStart gate, `.ready`-only assumption, or bidirectional propagation is used. A helper restart invalidates stale readiness; replace the pod if its main proc-root link is stale. Normal pod replacement reuses the same claim and original key.

## Other key modes — explicit, mutually exclusive

Use only one `keyDelivery.mode`: `curl` (default), `sealed`, or `insecureSecret`. Invalid/missing/conflicting sources fail render validation.

### Genuine CoCo sealed token

**Requires corrected upstream debug initdata and supported guest-local public signing trust**, tracked in [coco-pattern #153](https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162). The reviewed stock pattern does not provide that complete prerequisite. Charts assume the fix is supplied externally; they do not mutate shared initdata, add a KBS signing-key resource, or silently disable token-signature verification. Regenerate/propagate measured initdata, update trusted reference values/policy as required, and recreate pods after changes.

Prepare an actual signed vault token outside this repository with the release-matched CoCo `secret` CLI and protected private P-256 JWK. Its public vault metadata identifies `kbs:///default/kbsres1/key3` (or the configured resource). The token has `sealed.<base64url-header>.<base64url-payload>.<base64url-signature>` syntax, uses ES256 and a `kid` matching the guest-local public JWK. Extract exactly one token from CLI output: the CLI may print warning text before it. A bare URI or a plaintext placeholder Secret is **not** a sealed token.

```sh
oc --context "$CTX" -n "$NS" create secret generic storage-envelope --from-file=envelope=/protected/envelope.txt
helm install sealed ./block-storage-encrypted --kube-context "$CTX" -n "$NS" \
  --set keyDelivery.mode=sealed --set keyDelivery.sealed.existingSecret.name=storage-envelope
```

Kata recognizes the Secret-backed `PASS=sealed...` value and asks CDH to verify/unseal it before starting the helper. The helper receives plaintext only inside the guest, validates its byte contract and rejects still-sealed tokens. It cannot independently prove whether an operator-supplied source was sealed before Kata transformed it; provision the source correctly and verify both a valid token and tampered-token denial. Helm validates transport shape, not cryptographic signatures.

Alternatively supply `keyDelivery.sealed.envelope` via a protected local override file outside the chart; then the chart owns only the envelope Secret and deletes it on uninstall. An existing envelope Secret is externally managed and retained. Never commit a private JWK or plaintext key.

### Insecure standard Kubernetes Secret

This deliberately exposes key material to Kubernetes administrators; LUKS remains encrypted at rest, but **key delivery is not attestation-protected**. Supply the original equivalent passphrase through an existing Secret, never a chart value or expanded CLI key argument:

```sh
oc --context "$CTX" -n "$NS" create secret generic storage-test-key --from-file=passphrase=/protected/passphrase
helm install insecure ./block-storage-encrypted --kube-context "$CTX" -n "$NS" \
  --set keyDelivery.mode=insecureSecret --set keyDelivery.insecureSecret.name=storage-test-key
```

## Common configuration and images

Every field is commented in `values.yaml` and validated by `values.schema.json`. Common defaults: `runtimeClassName=kata-cc`, `initdata.mode=configMap`, `initdata.configMapName=debug-initdata`, `storage.mountPath=/mnt/storage`, `storage.size=1Gi`, null `storage.storageClass` (cluster default), and startup timeout/poll of 900/2 seconds. Empty class is rejected; explicit classes must support the same Block/Delete semantics.

Initdata overrides: select another ConfigMap, or set both `initdata.mode=inline` and `initdata.encoded` through a protected override file. Inline data takes precedence over pattern injection. `clusterDefault` mode explicitly omits selection annotations and skips pattern injection. A policy denying exec probes prevents Ready status; no policy is relaxed automatically. `--logs-only` can collect startup diagnostics without exec, not full readiness/mount/encryption acceptance.

`podLabels`, `podAnnotations`, `resourceLabels`, `resourceAnnotations` preserve reserved identity/ownership fields. Role resource requests/limits are configurable; main defaults reserve 2560Mi for 2048Mi guest RAM plus overhead, helper limits 256Mi. Keep limits compatible with actual VM and crypto memory. `serviceAccount.name` is an existing-account reference only when `create=false`; custom SCC references use `security.sccBinding.name`.

| Role | Default image |
|---|---|
| Main application and encryption helper | `registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1` |
| Curl retrieval init (curl mode only) | `registry.access.redhat.com/ubi9/ubi:9.6` |

Override full `images.application`, `images.storageHelper`, and `images.utility` references for disconnected use. Mirror tested artifacts and configure guest registry CA/auth/proxy plus attestation collateral. Do not assume host IDMS/ITMS settings reach the guest. No image builds or startup package downloads occur here.

## Verification and logs

Expected sequence: `storage_wait`, `storage_accessible`, then `file_created` (`created=true, verified=true`) or, on replacement, `file_existing_verified` (`created=false`). Prose is `This file demonstrates persistent storage for this confidential container example.` plus one newline. Its path is stable per namespace/chart/release. Mismatch/access/readback/mount/key failures are explicit and never overwrite existing content; a supervisory I/O timeout reports creation state as unknown instead of falsely claiming no write happened.

```sh
python3 -m venv .venv
.venv/bin/python3 -m pip install -r block-storage-encrypted/tests/requirements.txt
PATH="$PWD/.venv/bin:$PATH" sh block-storage-encrypted/tests/run.sh
sh block-storage-encrypted/tests/check-images.sh --role storage
sh block-storage-encrypted/tests/check-images.sh --role utility
sh block-storage-encrypted/tests/check-prerequisites.sh --context "$CTX" --namespace "$NS" --release encrypted
sh block-storage-encrypted/tests/verify-live.sh --context "$CTX" --namespace "$NS" --release encrypted --replace-pods --confirm-disposable
```

Live scripts operate on installed releases, verify new pod UIDs, admitted initdata, same claim/PV, intended mount, prose, and LUKS. Use `--scc <name>` for a custom SCC. Prepare separate approved negative-test releases/inputs yourself; `--expect-failure --failure-reason unlock_failed` observes a specific failed unlock without modifying keys or storage. For a tampered sealed-token release, select `agent_unseal_failed`. Pending startup alone is not proof of denial. Record each mode's positive and negative outcomes; absent corrected trust means sealed live acceptance is blocked, not passed by mocks.

## Cleanup — permanently destroys the block data

`helm uninstall <release> --kube-context "$CTX" -n "$NS" --wait` deletes chart-owned objects/claim; a compatible Delete CSI provider removes the PV/backing volume asynchronously. It does not delete the original Trustee resource, externally supplied Secrets, namespace, SCC, storage class, initdata or registry credentials. Pod deletion alone preserves the claim/data.

For actual provider-confirmed deletion, `tests/verify-uninstall.sh` requires `--context`, `--namespace`, `--release`, `--confirm-destructive`, and `--backend-check /absolute/executable`. That trusted checker receives `(CSI driver, saved volume handle)` and must return zero only when the backend asset is gone. Missing evidence/timeouts fail, and no finalizers or shared policy are changed. Do not run against production data.

### Completed safety and verification contracts

Backend-check exit **0** means proven absent, **3** means still present/pending, and any other nonzero code means checker failure. The pending result is polled under the same deadline as Helm/PV cleanup. Cleanup uses actual Helm/controller ownership, not matching labels alone, and verifies referenced external resources remain unchanged.

Every role requires CPU/memory requests and limits; limits must cover requests, and main requests must reserve at least **2560Mi** for fixed guest RAM plus overhead. Unsafe system mount paths and floating image aliases are rejected. The helper installs cleanup before opening a mapper or publishing readiness, including errors after opening. Only verified-owned mappings/mounts are cleaned up; wrong existing mappings are never adopted.

The main prose check pins the intended filesystem view and rechecks it before reporting success. A later path replacement cannot redirect its writes into the temporary root filesystem. File failures name the complete filename; mount expiry includes the configured budget and an explicit skipped file check. No key or arbitrary existing content is reported.

For explicit cohort/mirror checks, this chart's independent validation tool supports:

```sh
python3 block-storage-encrypted/tests/live.py collection --context "$CTX" --namespace "$NS" --release encrypted \
  --cohort block-storage-plain:plain --cohort block-storage-encrypted:encrypted \
  --cohort nfs-direct:direct --cohort nfs-direct:other \
  --expected-mirror mirror.example:8443 --expected-initdata-mode configMap
```

Supply the actual mirror expectation, and optionally identify an already removed member with `--removed-member chart:release` after a separately approved operation. The verifier checks surviving members; it never removes a member automatically. Fully exec-denying policy support remains blocked pending the probe-policy decision; these tools and fixes do not add a runtime Python service or weaken policy.
