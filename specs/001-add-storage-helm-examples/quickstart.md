# Quickstart Validation Guide

These commands target the implemented independent charts/scripts. Local chart/shell fixtures and image inventories are validated; no live cluster, attestation, persistence or backend deletion is claimed. Run from the repository root. See [configuration](contracts/values.md), [runtime outcomes](contracts/runtime.md), [state model](data-model.md), and recorded [validation](validation.md).

**Status**: Phase 1 validation guide under the user's corrected-initdata assumption. Sealed-mode live validation requires the [upstream trust prerequisite](research.md#r7--genuine-sealed-secret-mode-upstream-prerequisite) to be actually available; no test may be marked passed merely because the upstream issue was filed.

## Prerequisites

- Helm 3, `oc`, Bash, ShellCheck, Python 3.12 and pinned test dependencies; a logged-in operator account authorized for workload creation.
- Prepared OpenShift 4.22+ bare-metal confidential runtime, Red Hat OSC 1.13, Trustee 1.2, compatible CSI provider, and `kata-cc` on TDX/SNP workers.
- A `Block`-capable default storage class with `Delete` reclamation, or a compatible explicitly selected class. Verify provider/backend deletion support, not merely the class field.
- `debug-initdata` with a nonempty `INITDATA` field in the workload namespace and working coco-pattern admission. The default pattern propagation list includes `kbs-access`, not arbitrary new namespaces.
- Release service accounts authorized for the documented in-guest mount permissions. Optional chart SCC-use bindings require administrator permission and remain restricted to the release account. Do not bind all accounts in the namespace.
- One Trustee encryption-key resource at `default/kbsres1/key3`, or supply another identifier, with policy/reference values and KBS trust configured. Do not require a separate attestation-status resource.
- For sealed mode, corrected debug initdata and a supported guest-local public JWK matching the signed token's `kid`, without another KBS resource. Track [upstream issue #153](https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162). Regenerate/propagate initdata and update expected attestation measurements/policy when upstream configuration changes; recreate pods to pick up the new configuration. If this prerequisite is absent, report live sealed-mode validation blocked, not passed.
- A writable NFS export reachable from the guest, allowing the workload's documented identity; supply the actual server/export below. Do not disable root squashing globally as a workaround.
- Every pinned role image pullable by the guest; registry CA, pull credentials, proxy and disconnected attestation collateral prepared in initdata/environment as required.

## 1. Offline render and fixture tests

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r block-storage-plain/tests/requirements.txt
export PATH="$PWD/.venv/bin:$PATH"
helm lint ./block-storage-plain
helm lint ./block-storage-encrypted
helm lint ./nfs-direct --set nfs.server=nfs.example.test --set nfs.exportPath=/exports/samples
bash ./block-storage-plain/tests/run.sh
bash ./block-storage-encrypted/tests/run.sh
bash ./nfs-direct/tests/run.sh
```

Expected: independent chart validation passes; invalid key modes, missing mode inputs, unsafe paths, reserved metadata overrides, incompatible image references, and accidental NFS PV/PVC renders fail the relevant tests. Fixture tests distinguish mount delay from an accessible root directory and never create the demonstration file before confirmed storage access.

## 2. Verify live prerequisites

```bash
export TEST_CTX=your-approved-disposable-context
export TEST_NS=kbs-access
oc --context "$TEST_CTX" get runtimeclass kata-cc
oc --context "$TEST_CTX" get configmap debug-initdata -n "$TEST_NS"
oc --context "$TEST_CTX" get configmap debug-initdata -n "$TEST_NS" -o jsonpath='{.data.INITDATA}' | wc -c
oc --context "$TEST_CTX" get storageclass
```

Expected: runtime exists, encoded initdata is nonempty, and the selected storage class supports the raw-block and cleanup requirements. An existing namespace is an external prerequisite and will not be deleted by a release.

## 3. Deploy all examples together

```bash
export NFS_SERVER=nfs.example.internal
export NFS_EXPORT=/exports/confidential-samples
helm install plain ./block-storage-plain --kube-context "$TEST_CTX" -n "$TEST_NS"
helm install encrypted ./block-storage-encrypted --kube-context "$TEST_CTX" -n "$TEST_NS"
helm install direct ./nfs-direct --kube-context "$TEST_CTX" -n "$TEST_NS" --set-string nfs.server="$NFS_SERVER" --set-string nfs.exportPath="$NFS_EXPORT"
oc --context "$TEST_CTX" rollout status deployment -n "$TEST_NS" -l app.kubernetes.io/instance=plain --timeout=30m
oc --context "$TEST_CTX" rollout status deployment -n "$TEST_NS" -l app.kubernetes.io/instance=encrypted --timeout=30m
oc --context "$TEST_CTX" rollout status deployment -n "$TEST_NS" -l app.kubernetes.io/instance=direct --timeout=30m
oc --context "$TEST_CTX" logs -n "$TEST_NS" -l app.kubernetes.io/instance=plain -c application --prefix=true
oc --context "$TEST_CTX" logs -n "$TEST_NS" -l app.kubernetes.io/instance=encrypted -c application --prefix=true
oc --context "$TEST_CTX" logs -n "$TEST_NS" -l app.kubernetes.io/instance=direct -c application --prefix=true
```

Expected for each: `storage_accessible` precedes `file_created`; `created=true`, `verified=true`, path, and fixed public prose are present. First NFS run may instead report `file_existing_verified` if that release's file remains from an earlier installation. No logs contain key material. Confirm admitted pods selected `debug-initdata` and contain injected encoded initdata; do not print the full encoded payload unnecessarily.

Run each example's `tests/verify-live.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release <name>` to verify the file on the intended storage, mount source, encryption state when relevant, and no persistent-volume interface for direct NFS. These require an installed release, explicit context, and suitable probe/exec policy. No infrastructure is auto-created and unrelated data is not deleted. An approved custom SCC can be selected with `--scc <name>`.

## 4. Prove pod replacement preserves data

```bash
sh ./block-storage-plain/tests/verify-live.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release plain --replace-pods --confirm-disposable
sh ./block-storage-encrypted/tests/verify-live.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release encrypted --replace-pods --confirm-disposable
sh ./nfs-direct/tests/verify-live.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release direct --replace-pods --confirm-disposable
```

Expected: scripts verify the initial pod, perform two ordinary pod deletions only after explicit disposable confirmation, and wait for new pod UIDs/readiness and unchanged bound claim/PV identities. Both replacement logs show `file_existing_verified`, `created=false`, and exact unchanged prose. Forced pod deletion is not used. Add `--expect-existing` if the initial pod's NFS file was already retained from an earlier deployment.

## 5. Verify key modes and initdata overrides

- Curl is the default and retrieves only the configured encryption resource through guest CDH.
- For sealed delivery, first verify corrected initdata/trust prerequisites, then prepare a genuine signed CoCo envelope using the release-matched external `secret` CLI and a private signing JWK kept outside the repository. Select exactly one `sealed.` token from CLI output, not warning text; store it in the referenced Secret's `envelope` field. Install a separate release with `--set keyDelivery.mode=sealed --set keyDelivery.sealed.existingSecret.name=<envelope-secret>`. Verify it references the same KBS encryption resource and repeat replacement tests. An invalid/tampered signature must fail; a plain URI or placeholder plaintext Secret is not a sealed-mode test. Do not bypass verification to make this check pass.
- For insecure delivery, prepare an existing Secret from a protected local file without putting the key into shell arguments, chart values, or source control. Install a separate release with `--set keyDelivery.mode=insecureSecret --set keyDelivery.insecureSecret.name=<key-secret>`. Its equivalent key remains externally managed after uninstall. Documentation must label this delivery insecure despite LUKS at rest.
- Validate alternate ConfigMap, inline encoded initdata supplied through a protected local values file, and `initdata.mode=clusterDefault` as separate disposable releases. Ensure inline selection is not overwritten by admission. The implemented probes require guest exec; a policy denying it prevents Ready status. `--logs-only` collects startup diagnostics without interactive exec, but is not healthy-readiness or independent mount/encryption acceptance. The chart never relaxes a restrictive override silently.

## 6. Negative and coexistence scenarios

Use disposable releases/volumes/exports with known synthetic data, never production storage.

| Scenario | Expected result |
|---|---|
| Missing/denied resource, empty key, wrong unlock key | No ready application, no unsafe fallback/reformat, no key logs. |
| Existing prose changed or file unreadable | Specific `startup_failed`, existing content preserved, no foreground application launch. |
| Absent file on read-only storage | `create_failed`, not `file_created`; existing correct file on read-only storage may verify successfully. |
| Delayed mount visibility | No file access before main-container `storage_accessible`; normal success only afterward. |
| Unreachable NFS or permanently unavailable mount | Bounded failed gate; `file_check=not_run`, no root-filesystem fallback file. |
| Helper stops/restarts | Readiness fails until current helper/mount is verified; no stale PID accepted. |
| Missing debug ConfigMap | Identifiable admission/prerequisite failure, no silent alternate policy. |
| Two plain releases; two NFS releases on one export | Distinct objects/selectors and NFS filenames; one release removal leaves others working. |
| Long similar release identities | Name-shortening hashes preserve release isolation. |

Render/schema checks may test policy and fixture outcomes offline, but key release, actual mount namespace access, provider persistence, and deletion require live evidence.

## 7. Disconnected validation

Create a protected local override file supplying full mirror references for every consumed `images.*` role. Mirror the exact tested artifacts, preserve architecture, and configure guest-side registry trust/authentication and attestation dependencies. Install each chart with `-f <mirror-values-file>` in an environment without public registry/package access. Repeat steps 3–6; rendered/workload images must contain only approved mirror references. No startup package manager command is allowed.

## 8. Destructive uninstall verification

**Warning: uninstalling either block release permanently deletes its claim and backing volume.**

Before deletion, each `tests/verify-uninstall.sh` records the release-owned object list and bound PV/CSI backend identifiers. It must require an explicit destructive-test flag, uninstall only its named disposable release, then wait for namespaced objects and PV removal and require provider-specific backend deletion evidence.

For block releases, provide `BACKEND_CHECK` as the absolute path to a trusted executable accepting `(CSI driver, saved volume handle)` and returning zero only when the provider confirms the asset is absent. No adapter is fabricated for an unspecified provider; the verifier refuses block deletion without it. NFS cleanup needs no backend adapter because the export is unowned and preserved.

```bash
sh ./block-storage-plain/tests/verify-uninstall.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release plain --confirm-destructive --backend-check "$BACKEND_CHECK"
sh ./block-storage-encrypted/tests/verify-uninstall.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release encrypted --confirm-destructive --backend-check "$BACKEND_CHECK"
sh ./nfs-direct/tests/verify-uninstall.sh --context "$TEST_CTX" --namespace "$TEST_NS" --release direct --confirm-destructive
```

Expected: zero release-owned objects or block backing volumes remain; no deletion of Trustee, referenced Secrets, debug-initdata, SCC/storage class, namespace, or external NFS data. Other releases still pass verification. Cleanup timeout or an unverified backend volume is a failed/incomplete check, not a reason to strip CSI finalizers or change global storage policy.
