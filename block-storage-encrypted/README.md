# Encrypted block storage

A small Helm example for guest-side LUKS2/XFS storage with one selected key-delivery mode.

## Follow the flow

1. [`templates/pvc.yaml`](templates/pvc.yaml) requests a raw Block/RWO claim.
2. Default curl mode runs [`scripts/fetch-key.sh`](scripts/fetch-key.sh), retrieving the configured resource through **guest-local CDH**, which performs Trustee attestation/authorization. Ordinary curl does not directly implement KBS attestation.
3. The native helper sidecar runs [`scripts/encrypted-storage.sh`](scripts/encrypted-storage.sh): inspect media, initialize only confirmed blank media or reopen compatible LUKS, verify the key/backing mapper, then mount XFS. Cleanup is installed before acquiring storage resources.
4. [`scripts/main.sh`](scripts/main.sh) verifies the current helper PID/start generation and mount. Shared PID namespaces do **not** share mount namespaces: application access uses the verified `/proc/PID/root/mnt/storage` view.
5. [`scripts/prose-file.sh`](scripts/prose-file.sh) pins that view and creates/readbacks prose if absent, or verifies matching existing prose without rewriting it. Readiness requires current storage and matching prose, not just a marker.

## Prerequisites

- Use an existing prepared workload namespace; commands below use `examples` as its name.
- Prepared bare-metal TDX/SEV-SNP OpenShift/OSC confidential-container cluster, `kata-cc`, Kubernetes 1.33+ native-sidecar baseline, raw Block/Delete storage class and image access/guest registry trust.
- Same-namespace coco-pattern `debug-initdata` or explicit initdata allowing mounts, shared-process filesystem access and supplied read-only exec probes. Fully exec-denying policy is unsupported; no implicit policy relaxation.
- One preconfigured Trustee encryption-key resource, default `default/kbsres1/key3`. Charts never provision Trustee resources. Keys are 1–1024 single-line printable ASCII bytes.
- An SCC permitting lab-only privileged guest operations. The optional SCC binding is administrator opt-in, restricted to this release's account; debug policy/shared PID privileges are not production key isolation.
- **Sealed mode additionally requires externally corrected initdata/guest-local signing trust** and genuine signature-verified CoCo vault tokens. Stock debug initdata is not assumed to provide this. No verification bypass or extra Trustee resource is introduced.

## Try it (on your disposable test environment)

```sh
helm install encrypted ./block-storage-encrypted --namespace examples
oc logs deployment/encrypted -c application -n examples
```

Expect `event=file_created`, or `event=file_existing_verified` after replacing only the selected test pod. Failures emit `event=startup_failed` with a stage/reason; key bytes and arbitrary file contents are never logged. The native helper retains private guest-memory curl key state for its restarts; pod deletion destroys that state, and a new pod retrieves its key again.

## Choose exactly one key mode

| Mode | Essential values | Meaning |
|---|---|---|
| `curl` (default) | `keyDelivery.resourcePath`; leave `secret.name` empty | Attested retrieval through guest CDH at loopback port 8006; no external plaintext curl or fallback. |
| `sealed` | `keyDelivery.mode=sealed`, `secret.name`, `secret.key` | Existing Secret contains genuine signed `sealed.…` vault token for the **same resourcePath**; Kata/CDH unseal PASS before helper startup. Not Bitnami Sealed Secrets. |
| `insecureSecret` | `keyDelivery.mode=insecureSecret`, `secret.name`, `secret.key` | Explicitly insecure existing Kubernetes Secret supplies PASS; no attestation claim. |

The reference paths above are under `keyDelivery` (e.g. `keyDelivery.secret.name`). The chart owns neither Secret; it never creates an inline token Secret. Prepare matching tokens/trust externally. Do not put plaintext keys into Helm values or command arguments. A still-sealed PASS fails instead of being used as an encryption key; modes never fall back to one another.

## Essential environment values

[`values.yaml`](values.yaml) exposes only class/capacity, runtime/initdata, images/pull references, timeout, actual container resources and optional SCC-use binding. `images.storageHelper` covers application and helper; `images.utility` covers curl. Override both for disconnected curl operation; no package downloads at startup.

`initdata.encoded` takes precedence over `initdata.configMapName` (`debug-initdata` default); empty ConfigMap name with absent encoded data selects cluster default. Keep application memory sized for the 2048Mi guest plus overhead (default 2560Mi). Paths and 2s polling are fixed. Each release gets its own account, claim and prose identity; no upgrade/naming framework.

## Validate and clean up

Run `sh block-storage-encrypted/tests/run.sh` from repository root with Helm, Python and pinned `tests/requirements.txt` tools available. It checks all three mode renders and static shell/source/package properties only; it does not prove attestation, unsealing, encryption or persistence on a cluster.

**Testing only: uninstall/reinstall for chart revisions; upgrades are unsupported.** `helm uninstall encrypted -n examples` removes owned resources/claim, with backing volume/data reclaimed by compatible Delete provisioning. There is no backend-deletion hook. Existing key/pull Secrets, initdata and Trustee infrastructure remain untouched. Replacing only a pod preserves the original claim/data.
