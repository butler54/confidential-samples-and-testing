# Phase 0 Research: Confidential Storage Helm Examples

**Date**: 2026-10-08. **Status**: Complete under the user's direction to presume corrected upstream debug initdata. The current upstream gap is a recorded external dependency, not a completed fix. No images were executed and no cluster was accessed.

## R1 — Versioned Red Hat and pattern baseline

**Decision**: Target OpenShift 4.22+ bare metal, OSC Operator 1.13.0, Trustee Operator 1.2.0, and documented `osc-storage-helper:1.13.1`. Record coco-pattern revision `aa04a093268be8ac92174313848a4c44298fbc41` as the inspected compatibility reference. Guest-components source inspected by delegated research is v0.20.0 via OSC 1.13 branches; verify installed guest binaries before claiming live compatibility.

**Rationale**: Matches the user-supplied downstream documentation and current pattern versions rather than assuming staged `latest` images are stable. Operator and image patch versions need not match.

**Alternatives considered**: Historical OSC versions, floating pattern/main references, Azure peer-pods; excluded from this initial compatibility scope.

**Evidence**: [pattern baseline](https://github.com/validatedpatterns/coco-pattern/blob/aa04a093268be8ac92174313848a4c44298fbc41/values-baremetal.yaml), [OSC versions](https://github.com/openshift/kata-containers/blob/osc-release-v1.13/versions.yaml), [Red Hat configuration/storage documentation](https://docs.redhat.com/en/documentation/openshift_sandboxed_containers/1.13/html/deploying_confidential_containers_on_bare-metal_servers/configure-cc-overview_metal-cc#encrypt-the-block-volumes_metal-cc).

## R2 — Pattern initdata ownership and overrides

**Decision**: Reference existing same-namespace `debug-initdata` through the pod-template annotation; never claim ownership of a synchronized pattern ConfigMap. Inline mode uses the runtime annotation and skip-injection label; cluster-default mode omits selection annotations and opts out of pattern injection. Updating an external ConfigMap requires pod recreation to pick up admission-generated initdata.

**Rationale**: Inspected policy mutates Pods on CREATE, only when the inline annotation is absent. Propagation defaults include `kbs-access`, `hello-openshift`, and `gpu-workload`, not arbitrary namespaces. The chart remains independently deployable against documented infrastructure prerequisites.

**Alternatives considered**: Chart-owned hard-coded debug initdata, mutation of pattern-managed ConfigMaps, or assuming all namespaces inherit the ConfigMap. Rejected due to ownership collisions, stale policy/trust configuration, and unsupported propagation assumptions.

**Evidence**: [injection policy](https://github.com/validatedpatterns/coco-pattern/blob/aa04a093268be8ac92174313848a4c44298fbc41/charts/all/coco-kyverno-policies/templates/inject-coco-initdata.yaml), [propagation values](https://github.com/validatedpatterns/coco-pattern/blob/aa04a093268be8ac92174313848a4c44298fbc41/charts/all/coco-kyverno-policies/values.yaml). Pattern-owned labeled ConfigMaps also carry version/algorithm/policy/AA/CDH source fields; charts need not synthesize such resources when referencing existing ones.

## R3 — NFS image and application topology

**Decision**: Use the official Red Hat storage-helper image for plain-block and NFS tool-complete main containers; after mount/prose verification, keep a simple foreground process running. HTTP serving is not required by the spec. The encrypted main container can use the same tool-complete image while its native helper owns the LUKS mount. All consumed image roles retain full-reference overrides.

**Rationale**: Official source installs `nfs-utils`, `xfsprogs`, `util-linux-core`, and `cryptsetup`. This avoids both new external builds and assuming httpd includes mount/filesystem-verification tools. Direct NFS in the main container needs no shared PID namespace or cross-container propagation.

**Alternatives considered**: HTTP image with an NFS sidecar; larger and unnecessary for a logging/persistence demonstration. Custom UBI NFS-client build; not required by inspected official package inventory. Runtime `dnf`/`microdnf`; prohibited. Existing staged httpd digest remains a future optional application adaptation, not the initial smallest design.

**Evidence**: [Red Hat catalog](https://catalog.redhat.com/en/software/containers/openshift-sandboxed-containers/osc-storage-helper/691743860bb721cbe3bbec12) maps researched `1.13.1-1784814603` to source commit `617f70ce2225e036976c94783e1812a1dec4e41c`; [Containerfile](https://github.com/openshift/confidential-compute-artifacts/blob/617f70ce2225e036976c94783e1812a1dec4e41c/containerfiles/storage-helper/Containerfile), [locked RPM inventory](https://github.com/openshift/confidential-compute-artifacts/blob/617f70ce2225e036976c94783e1812a1dec4e41c/containerfiles/storage-helper/rpms.lock.yaml).

**Implementation acceptance checks**: Verify exact selected image digest/architecture contains `mount.nfs`, mount/filesystem inspection tools, shell/file-check utilities and bounded-operation tooling; verify guest-kernel NFS support. Source evidence is not live binary execution. Missing expected tools is a failed image preflight, not authorization to install packages at startup. Registry-authenticated digest resolution and role-image tool execution remain implementation validation obligations.

## R4 — Mount visibility and lifecycle

**Decision**: Plain-block main mounts the init-formatted raw device itself; NFS main directly mounts the external export. Encrypted storage follows the supported native helper/shared-PID topology with memory-backed `/dev/shm` and dynamic helper PID. Main startup reads the current PID, checks helper mountinfo/source/filesystem, resolves `/proc/<pid>/root/mnt/storage`, and verifies access through the application-visible path before prose operations. Do not use postStart as an ordering gate.

**Rationale**: Shared PID namespaces permit `/proc/<pid>/root` access but do not merge mount namespaces. A ready marker or PID file alone can be stale. Mount-source verification and access in the main container prevent false success on temporary storage.

**Alternatives considered**: Hard-coded PID 2, process enumeration plus `eval`, fixed sleeps, main-namespace `mountpoint` applied to a proc-root symlink, and `Bidirectional` mount propagation. Rejected as unreliable or unnecessarily propagating mounts toward the host.

**Evidence**: [helper documentation](https://github.com/openshift/confidential-compute-artifacts/blob/617f70ce2225e036976c94783e1812a1dec4e41c/containerfiles/storage-helper/luks_helper.md), [Kubernetes shared-process filesystem access](https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/), [postStart concurrency](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/), [mount propagation](https://kubernetes.io/docs/concepts/storage/volumes/#mount-propagation).

**Limits**: Helper restart inside one Pod is separate from whole-pod replacement. Re-read current identity, fail readiness when it changes, and require safe relinking or pod replacement; do not claim automatic recovery from a stale PID. NFS hard-mount I/O can hang, so supervisor deadlines must include individual file/mount checks. Node/CSI recovery may take longer than the in-container startup gate.

## R5 — LUKS utility safety

**Decision**: Consume Red Hat's helper utilities through a small audited chart-local shell state machine calling the same image's `cryptsetup`/XFS utilities. Do not call the binary's unsafe `format-disk` fallback. Add no force-format flags and never equate an inspection error with a blank disk. The wrapper publishes the current helper PID after verified mounting so the main container can use the documented shared-process filesystem access mechanism.

**Rationale**: Inspected helper skips formatting for existing LUKS/XFS, but any failed `isLuks` can lead to `luksFormat`, failed/non-XFS `blkid` can lead to `mkfs`, existing mapper reuse does not validate backing device, and accepted mount-busy errors do not validate source. Its wait-ready helper reads the PID once. Blindly copying the official example would violate FR-009/FR-010 safety requirements.

**Alternatives considered**: Unwrapped binary, staged `set -ex` script, force-format on every restart, fixed mapper reuse; rejected. Forking/building a replacement helper image here; prohibited and unnecessary if utilities suffice.

**Evidence**: [pinned helper implementation](https://github.com/openshift/confidential-compute-artifacts/blob/617f70ce2225e036976c94783e1812a1dec4e41c/containerfiles/storage-helper/luks_main.go).

**Acceptance gates**: Test recognized incompatible signatures, probe errors, wrong existing mapper, wrong key with an already open mapper, and stale mount state. Do not accept nominal successful helper exit as proof of safe initialization. No broad host `/dev` relabeling; diagnose driver-specific SELinux failures without disabling enforcement.

## R6 — Curl retrieval and passphrase transport

**Decision**: Fetch only `http://127.0.0.1:8006/cdh/resource/default/kbsres1/key3` (configurable resource segments) using `curl --fail --silent --show-error`, loopback proxy bypass and finite connect/overall timeout. Stage privately in guest memory; validate a nonempty bounded single-line printable-ASCII passphrase, rejecting NUL/newlines without printing contents. Export `PASS` using shell builtin assignment and `exec` helper; no `env PASS=<expanded-key>` argument and no tracing.

**Rationale**: CDH performs attestation/KBS authorization. Ordinary curl does not implement KBS's attestation protocol. Helper `PASS` integration supplies cryptsetup through stdin but still retains environment-based guest exposure; debug policy/shared PID privilege makes this a lab, not a production isolation guarantee.

**Alternatives considered**: Direct anonymous Trustee access, logging response bodies, stdout/webroot staging, key command arguments, invented REST `/cdh/unseal`; rejected. No attestation-status fetch is needed, preserving the one-resource premise.

**Evidence**: [Red Hat attestation resource access](https://docs.redhat.com/en/documentation/openshift_sandboxed_containers/1.13/html/deploying_confidential_containers_on_bare-metal_servers/configure-cc-overview_metal-cc#verifying-attestation_metal-cc), [REST router](https://github.com/confidential-containers/guest-components/blob/v0.20.0/api-server-rest/src/router.rs), [helper source](https://github.com/openshift/confidential-compute-artifacts/blob/617f70ce2225e036976c94783e1812a1dec4e41c/containerfiles/storage-helper/luks_main.go).

**Image decision**: Utility role uses versioned full Red Hat UBI (`registry.access.redhat.com/ubi9/ubi:9.6`) subject to exact tool/digest verification before merge; the helper Containerfile does not explicitly install curl. No production workload compiler/sealing tool is required. Any actually necessary augmented image must be built in `butler54/containers`, never here or at startup.

## R7 — Genuine sealed-secret mode: upstream prerequisite

**Confirmed mechanism**: Operator prepares a `sealed.<base64url-header>.<base64url-payload>.<base64url-signature>` token using release-matched `secret` CLI, transported as Kubernetes Secret `PASS` environment data. Kata Agent recognizes `sealed.`, calls CDH ttRPC `UnsealSecret`, and the vault provider fetches the same KBS encryption resource. The v0.20.0 vault payload has `version: "0.1.0"`, `type: "vault"`, `provider: "kbs"`, `name: "kbs:///default/kbsres1/key3"`, and empty provider settings/annotations. Header/payload/signature use unpadded base64url; signature verification uses ES256/P-256 and header `kid`.

**Current upstream gap**: Verified mode needs the public signing JWK from another KBS resource or `/run/confidential-containers/cdh/sealed-secret/<kid>` in the guest. Stock debug initdata has no documented provisioning mechanism for that local verification file. Arbitrary initdata fields are not automatically written to arbitrary guest paths; credential fetch destinations differ. A second KBS key resource contradicts FR-012. The currently reviewed pattern therefore cannot be represented as having met the complete verified-mode prerequisite.

**Decision (user-authorized)**: Proceed assuming corrected upstream debug initdata and its supported guest-local verification-key provisioning are supplied externally. Retain one KBS resource and signature-verified vault tokens; charts only consume the corrected configuration and signed envelope. Report invalid/unavailable trust as a failed prerequisite. Do not patch shared pattern configuration or pretend current stock initdata already works.

**Upstream tracking**: The user chose to add these findings to existing [issue #153](https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162) rather than create a duplicate. The source-based report and requested fix are preserved in [upstream-issue.md](upstream-issue.md). An upstream issue submission is not confirmation of a fix.

**Alternatives considered (not authorized)**:

1. Explicit lab-only relaxation: configure selected debug initdata with CDH `skip_sealed_secret_verification = true`. This skips token-signature verification, not attestation/KBS key-release authorization. Charts must not silently mutate a shared pattern ConfigMap; operator approval and explicit provisioning are required.
2. Permit a second KBS resource holding the public verification JWK, while keeping exactly one encryption-key resource. This preserves verified token integrity but changes the current resource-count constraint.
3. Require identification and proof of the guest-local provisioning mechanism before any design proceeds. The user instead authorized planning against corrected upstream configuration as an external prerequisite; live release acceptance still requires that proof.

**Alternatives rejected**: Plaintext placeholder `kbs-access-sealed` chart, bare URI environment values, Bitnami controller decryption, old fake-header tokens, or claiming debug mode already disables verification.

**Evidence**: [OSC Kata unseal_env](https://github.com/openshift/kata-containers/blob/osc-release-v1.13/src/agent/src/confidential_data_hub/mod.rs), [secret verification](https://github.com/openshift/confidential-containers-guest-components/blob/osc-release-v1.13/confidential-data-hub/hub/src/secret/mod.rs), [vault provider](https://github.com/confidential-containers/guest-components/blob/v0.20.0/confidential-data-hub/hub/src/secret/layout/vault.rs), [CDH configuration](https://github.com/confidential-containers/guest-components/blob/v0.20.0/confidential-data-hub/hub/src/config.rs), [initdata extraction](https://github.com/openshift/kata-containers/blob/osc-release-v1.13/src/agent/src/initdata.rs), [sealing CLI](https://github.com/confidential-containers/guest-components/blob/v0.20.0/confidential-data-hub/hub/src/bin/secret_cli.rs). CLI may print a warning before its token; extract/validate exactly one token rather than storing all stdout as the sealed Secret.

## R8 — Ownership, cleanup and automated validation

**Decision**: Release-owned PVCs, no keep hooks/annotations, stable names across replacement, `Recreate` Deployments; pre-existing provider class must use `Delete` with working backend reclamation. Verify actual backend deletion, not only Helm/claim/PV disappearance. External NFS export/files and referenced Secrets/ConfigMaps remain unowned.

**Rationale**: Kubernetes provider reclamation, not Helm itself, deletes backend storage. Chart must not change shared classes, strip CSI finalizers, or delete other releases' objects. Offline chart/shell tests complement, not replace, opt-in live confidential hardware and CSI tests.

**Alternatives considered**: Retain policy, StatefulSet-generated claims, ephemeral pod-owned claims, backend deletion by a broad-privilege hook, or NFS export deletion; rejected by specified replacement/uninstall semantics and least privilege.

**Evidence**: [PV reclaim semantics](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#reclaiming), [native sidecars](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).

## Gate Result

Storage/NFS/image-source questions have concrete design choices and explicit implementation verification gates. **R7 is resolved for planning by the user-authorized corrected-initdata prerequisite; Phase 0 passes under that explicit dependency.** Phase 1 contracts retain fail-closed signed-envelope behavior. No extra Trustee resource, implicit signature bypass, upstream fix completion, or live test success is claimed. Task generation may proceed, but complete live sealed-mode acceptance remains gated on corrected upstream configuration and verification-key provisioning.
