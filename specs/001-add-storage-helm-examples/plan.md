# Implementation Plan: Confidential Storage Helm Examples

**Branch**: `002-refine-storage-startup` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-add-storage-helm-examples/spec.md`. `.specify/feature.json` selects this directory independently of the git branch. Setup reported the original feature identifier as `BRANCH`; `git status` identifies the actual working branch shown above.

**Status**: Phase 0 and Phase 1 design complete under the user-authorized external prerequisite of corrected coco-pattern debug initdata. The upstream gap remains tracked in [issue #153](https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162); this is not evidence of a deployed fix or passing live validation.

## Summary

Deliver three independent root-level charts for plain raw-block storage, encrypted raw-block storage, and direct in-guest NFS mounting. Preserve baseline concepts but replace ad hoc Pods, hard-coded helper PIDs, `eval`, late postStart hooks, plaintext passwords, and floating images. Each Deployment has one replica and uses `Recreate`; the chart-owned block PVC outlives pod replacement but is removed on uninstall.

All examples select coco-pattern `debug-initdata` by default, retain explicit initdata/image overrides, and use a main-container startup gate that verifies access to the intended storage before creating or verifying a stable release-specific prose file. Logs distinguish creation, existing expected prose, and failure. Secret delivery uses a single enum selecting attested curl, genuine CoCo sealed delivery, or an explicitly insecure existing Secret.

## Technical Context

**Language/Version**: Helm 3 application charts (`apiVersion: v2`), Kubernetes YAML, JSON Schema draft-07 values validation, POSIX shell-compatible workload scripts; Python 3.12 for development-time render/contract tests, not a workload dependency.

**Primary Dependencies**: Red Hat OSC 1.13, Trustee Operator 1.2.0, existing `kata-cc` RuntimeClass, CSI raw-block provisioning, pattern Kyverno initdata admission, storage/helper tools supplied in pinned prebuilt images. No Helm dependencies or runtime package installation.

**Storage**: Chart-owned 1Gi `Block`/`ReadWriteOnce` claims, default storage class unless overridden; XFS, with LUKS for the encrypted sample; externally managed NFSv4.1 export for direct NFS. Selected CSI class/provider must reclaim PV/backend storage using `Delete`.

**Testing**: `helm lint`, values/negative render cases, YAML resource/selector/image-policy assertions, ShellCheck, shell entrypoint fixture tests, and opt-in live OpenShift verification including two pod replacements, all key modes, denied-key and mount-delay failures, disconnected deployment, and backing-volume deletion. Public CI must not imply live attestation validation if hardware/secrets are unavailable.

**Target Platform**: OpenShift 4.22+ bare metal, Intel TDX or AMD SEV-SNP; native sidecars supported. Compatibility baseline is coco-pattern commit `aa04a093268be8ac92174313848a4c44298fbc41`, which pins OSC Operator 1.13.0 and Trustee Operator 1.2.0. Default helper image version follows Red Hat's documented `1.13.1`; image version and Operator version are distinct. Historical pattern revisions, Azure peer-pods, GPU configurations, and production agent-policy hardening are not included.

**Project Type**: A collection of self-contained Helm workload examples and validation scripts.

**Performance Goals**: Demonstration correctness rather than throughput. Main-container mount gate defaults to 900 seconds with two-second polling; individual storage operations require bounded supervision. Live rollout/cleanup verification uses separately configurable deadlines because scheduling, image pulls, and CSI reclamation are asynchronous.

**Constraints**: No local container builds, new cluster operators, global storage/SELinux policy edits, sibling runtime dependencies, public startup package installation, secret logs, insecure key fallback, destructive reformatting, or file writes before main-container mount access. Required mount privileges are isolated to dedicated release accounts in the confidential guest and documented as lab exceptions to restricted-pod hardening; no host namespace or hostPath access.

**Scale/Scope**: Three charts; one replica each; three encrypted-key modes; all three plus another release in one namespace; exactly one pre-existing Trustee encryption resource. No shared writers, key rotation, NFS-server management, backup, HA, benchmarking, or retention mode.

### Resolved Research Decisions

- Resolved by user direction: build assuming upstream corrects debug initdata and supplies a supported signature-verification prerequisite without another KBS resource. The chart consumes a genuine signed vault envelope and the operator-provided corrected configuration; it does not provision the guest trust anchor, mutate shared initdata, or implicitly skip token verification. Until the upstream prerequisite is available and verified, live sealed-mode acceptance remains unmet, not silently skipped/passed.
- Resolved: official helper source/package inventory includes NFS utilities. Use tool-complete helper image as main for plain/NFS and encrypted file verification; no HTTP Service/Route is required.
- Resolved: helper has unsafe inspection fallbacks and stale-PID limitations. Use audited chart-local orchestration of the official image's cryptsetup/XFS utilities for encrypted initialization/reopen, not its unsafe `format-disk` fallback. Publish current helper identity only after mount verification; fail-closed preflight and live negative tests are mandatory.

Research choices and alternatives are documented in [research.md](research.md). All design decisions are resolved; actual image/tool inventory, hardware attestation, guest trust provisioning, persistence, and provider reclamation remain implementation/live acceptance checks rather than assumed successes.

## Constitution Check

*Gate before Phase 0 and again after Phase 1.*

| Principle | Pre-research assessment | Design obligation |
|---|---|---|
| I. Self-contained examples | Pass | Each chart includes its scripts, schema, docs, and tests; duplicate a small startup contract rather than depend on a sibling/library chart. |
| II. Helm-first delivery | Pass | All workloads/configuration expressed by charts; no Kustomize. Local validation/debug commands remain shell scripts. |
| III. Downstream-first dependencies | Pass | Red Hat helper source confirms NFS utilities; all workload roles use Red Hat images. |
| IV. External image builds | Pass | No Containerfile/build in this repository; any additional image must be defined/built in `butler54/containers` and consumed by maintained reference. |
| V. CI/CD and version discipline | Pass | Add CI for version/schema/shell/render regressions and pin development tools; live checks are explicit and do not fabricate success. |
| VI. Simplicity and explainability | Pass | One Deployment/claim per block release, one external export per NFS release; default no Service/Route because logs and debug execution suffice. |
| Delivery constraints | Pass | Keep deployment content within each root-level example; only CI and repository README are shared. |

Post-design status: **Pass with documented external prerequisite**. The user authorized proceeding on corrected upstream initdata, not an extra KBS resource or implicit signature bypass. No constitution exceptions, local image builds, cluster changes, or live-test success are claimed. A release cannot satisfy full acceptance until sealed mode is exercised against corrected configuration.

## Project Structure

### Documentation (this feature)

```text
specs/001-add-storage-helm-examples/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── values.md
│   └── runtime.md
└── checklists/requirements.md
```

`tasks.md` is generated by `/speckit.tasks`, not this planning command.

### Source Code (repository root; implementation targets)

```text
README.md
.github/workflows/validate-examples.yml
block-storage-plain/
├── Chart.yaml
├── values.yaml
├── values.schema.json
├── README.md
├── scripts/                   # mount/helper, main startup, readiness
├── templates/                 # helpers, Deployment, PVC, SA, scripts CM, optional SCC-use RBAC, NOTES
└── tests/                     # render fixtures, shell fixtures, opt-in live validation
block-storage-encrypted/
├── Chart.yaml
├── values.yaml
├── values.schema.json
├── README.md
├── scripts/                   # additionally key delivery and encryption preflight
├── templates/                 # additionally optional sealed-envelope Secret
└── tests/
nfs-direct/
├── Chart.yaml
├── values.yaml
├── values.schema.json
├── README.md
├── scripts/                   # direct mount, main startup, readiness
├── templates/                 # no PV/PVC/NFS Kubernetes volume
└── tests/
staging/                       # existing user samples remain untouched
```

**Structure Decision**: Charts live directly in their example directories so `helm install <release> ./<example>` works. Script ConfigMaps package scripts from that same chart directory. Shared CI invokes independent per-chart tests; identical contracts are tested across the collection without introducing a shared deployment dependency.

## Delivery and Validation Design

1. Define strict values/schema and naming helpers. Use a readable prefix plus a hash of full namespace/example/release identity; reserve suffix length before shortening. Keep `.Release.Namespace` authoritative; no alternate namespace value or unscoped full-name override.
2. Render default debug initdata only in the pod template; inline/cluster-default modes explicitly opt out of pattern injection. Do not create or own pattern-managed ConfigMaps. `kbs-access` is a useful existing pattern namespace because the pinned propagation list includes it; arbitrary namespaces require operators to provision their ConfigMaps/policies first.
3. Use a release-owned ServiceAccount, API-token automount disabled, and optional namespaced SCC-use binding to one pre-existing SCC. Default binding creation is disabled so install does not silently grant privileges. No cluster-wide binding or new SCC; roles grant only `use` of that SCC.
4. Use mount/helpers with dynamic identity and a memory-backed control directory. The main entrypoint—not postStart—waits for matching intended source and application-visible access, then runs the prose-file state machine. Deployment startup/readiness probes must check that same view. Never treat `.ready` on its own as mount proof.
5. Preflight raw and mapped devices before initialization. Distinguish an empty device from probe errors/unknown signatures; permit compatible reuse, refuse destructive conversion. Acquire keys before mutating storage; never trace or print the passphrase. Implement the encrypted state machine in a small chart-local wrapper using Red Hat's cryptsetup/XFS utilities, not the binary's unsafe inspection-error formatting fallback. Verify the key even when a mapper already exists, validate its backing device and mount source, and publish the helper's current PID/generation after successful preparation.
6. Do not use a rolling update for `ReadWriteOnce` storage. A pod replacement reuses the stable PVC and requires reattestation/key retrieval as appropriate; a helper restart invalidates stale control state and readiness until the current mount is verified.
7. Apply image overrides to every consumed role, include guest registry CA/credential/proxy prerequisites, and verify no remaining public-registry references in disconnected renders. Do not assume node IDMS/ITMS settings automatically apply inside the confidential guest.
8. Validate uninstall at three levels: release-owned namespaced objects gone, bound PV gone, provider-confirmed backing volume gone. NFS files and external infrastructure remain; warn that block uninstall is destructive. No manual CSI finalizer removal or global reclaim-policy modification.

## Requirement Traceability

| Requirement group | Design/test evidence |
|---|---|
| FR-001–FR-006 | Independent chart packages, strict values, pattern admission contract, overrides and metadata negative cases. |
| FR-007–FR-010 | Raw block claims, blank/compatible/incompatible preflight fixtures, mount/readback checks, retained-data replacement. |
| FR-011–FR-013 | Enum/source validation, genuine sealed and local-CDH integrations, mode matrix, denied/empty/wrong-key tests, log redaction. |
| FR-014–FR-017 | Direct NFS mount, image/tool matrix, no PVC/NFS-volume render assertion, offline startup and image-reference tests. |
| FR-018–FR-022 | Main-container readiness, scoped permissions, README/NOTES, replacement and actual CSI deletion verification. |
| FR-023–FR-026 | Startup fixtures and live logs for creation/existing/mismatch/access error, delayed propagation, timeout, release-isolated NFS filenames. |
| FR-027 | Upstream issue linkage, corrected-initdata prerequisite, signed-token fail-closed tests, no chart mutation or implicit signature bypass. |

## Complexity Tracking

No constitution violations accepted. Privileged in-guest mounting and debug agent policy are required demonstration constraints, not assertions of production restricted-pod compliance. Research findings must distinguish confirmed support from executable acceptance checks still required before merge.
