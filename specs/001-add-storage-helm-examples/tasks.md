---
description: "Executable implementation tasks for confidential storage Helm examples"
---

# Tasks: Confidential Storage Helm Examples

**Input**: Design documents from `specs/001-add-storage-helm-examples/`.

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [values contract](contracts/values.md), [runtime contract](contracts/runtime.md), and [quickstart.md](quickstart.md).

**Tests**: Required explicitly by FR-021 and FR-026, including schema/render checks, startup/storage fixtures, and opt-in live verification. Author negative fixtures before their implementation; distinguish test-authoring completion from a passing suite. Never mark hardware, attestation, disconnected, or backend-deletion tests passed without evidence.

**Organization**: Shared setup and foundation, then US5/US1/US2 (all P1), US3/US4 (P2), then polish. US5 comes first among equally prioritized P1 stories because its startup gate must exist before any example can safely touch storage. This does not change spec story identifiers or priorities.

## Format: `[ID] [P?] [Story] Description`

- Every task starts with an unchecked checkbox and sequential `Tnnn` identifier.
- `[P]` identifies work on different files that can run concurrently after the explicitly stated prerequisites; it does not waive those prerequisites.
- Story labels map to the original specification: US1 plain block; US2 encrypted block; US3 direct NFS; US4 common configuration/coexistence; US5 startup persistence logs.
- All file paths below are repository-relative. Each example owns its scripts/tests/configuration; no sibling chart, shared runtime library, local image build, or Kustomize is introduced.

## Path Conventions

- Charts: `block-storage-plain/`, `block-storage-encrypted/`, `nfs-direct/`, each installed directly as a Helm chart.
- Each contains `Chart.yaml`, `values.yaml`, `values.schema.json`, `templates/`, `scripts/`, `tests/`, and `README.md`.
- Test dependencies/runners are local to each chart; shared automation is limited to `.github/workflows/validate-examples.yml`.
- Evidence is recorded in `specs/001-add-storage-helm-examples/validation.md` without key material, private JWKs, encoded private configuration, or sensitive environment data.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish self-contained chart packages and reproducible development tooling without touching the staged samples.

- [X] T001 Create `block-storage-plain/Chart.yaml`, `block-storage-encrypted/Chart.yaml`, and `nfs-direct/Chart.yaml` as uniquely named Helm v2 application charts at version `0.1.0`, with each chart's local `templates/`, `scripts/`, and `tests/` directories; preserve all existing `staging/` content.
- [X] T002 Configure independent test entrypoints in `block-storage-plain/tests/run.sh`, `block-storage-encrypted/tests/run.sh`, and `nfs-direct/tests/run.sh` with pinned Python 3.12 YAML/test dependencies in each `tests/requirements.txt`, Helm/schema/render checks, and POSIX-shell ShellCheck invocation; no live cluster access in the default runner.
- [X] T003 Add role-image capability checks to `block-storage-plain/tests/check-images.sh`, `block-storage-encrypted/tests/check-images.sh`, and `nfs-direct/tests/check-images.sh`, and record source/tag/digest/architecture findings in `specs/001-add-storage-helm-examples/validation.md`: verify the selected Red Hat helper's mount/XFS/cryptsetup/NFS/file/timeout tools and the full UBI image's curl/validation tools without building images here or installing packages at workload startup; report registry-auth/tooling limitations honestly.

**Checkpoint**: Three distinct chart packages and standalone test runners exist. An image missing required tools blocks that affected runtime path; any additional build requires a separately authorized change in `butler54/containers`.

**Implementation checkpoint (2026-10-08)**: T001–T002 completed. T003 capability-check scripts are authored and ShellCheck passes, but registry inspection of the default helper returned unauthorized; actual digest/architecture/tool inventory is not verified. Implementation halted before Phase 2 under the sequential-task failure rule. See `specs/001-add-storage-helm-examples/validation.md`; no live deployment or volume deletion occurred.

**Resume checkpoint (2026-10-08)**: User configured registry authentication. All four Linux/amd64 role-capability checks now pass and image identities are recorded in `validation.md`; T003 is complete and Foundation may proceed. This does not establish guest-kernel, attestation, mount, persistence, or backend-deletion acceptance.

**Implementation outcome (2026-10-08)**: Foundation, all three chart implementations, startup safety, documentation, image capability checks, offline fixtures, packaging/isolation checks and CI are complete. 57/61 tasks are checked. T028, T040, T048 and T056 remain unchecked because no disposable cluster/export, corrected sealed trust or provider-backed cleanup evidence has been supplied; no live acceptance is claimed.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the shared configuration/resource identity contracts in each independent chart before story work begins.

- [X] T004 Define commented common defaults in `block-storage-plain/values.yaml`, `block-storage-encrypted/values.yaml`, and `nfs-direct/values.yaml` from `contracts/values.md`: `kata-cc`, ConfigMap-mode `debug-initdata`, full versioned role-image overrides, `/mnt/storage`, 900-second/two-second startup settings, role resources accounting for guest RAM/overhead, and optional SCC binding disabled by default; add the documented storage/key/NFS defaults without plaintext keys.
- [X] T005 Implement common validation in `block-storage-plain/values.schema.json`, `block-storage-encrypted/values.schema.json`, and `nfs-direct/values.schema.json`, rejecting invalid initdata modes, missing selected inputs, unsafe paths/control characters, conflicting reserved metadata, floating image references, invalid timeouts, and an empty-string storage class; keep default unused fields compatible with valid mode selection.
- [X] T006 Implement release-isolated naming, immutable selectors, reserved metadata conflict checks, and ConfigMap/inline/cluster-default annotation precedence in `block-storage-plain/templates/_helpers.tpl`, `block-storage-encrypted/templates/_helpers.tpl`, and `nfs-direct/templates/_helpers.tpl`; include a hash of full namespace/chart/release identity before shortening, reserve resource-suffix space, and keep `.Release.Namespace` authoritative.
- [X] T007 Implement dedicated ServiceAccounts in `block-storage-plain/templates/serviceaccount.yaml`, `block-storage-encrypted/templates/serviceaccount.yaml`, and `nfs-direct/templates/serviceaccount.yaml`, with optional namespace-scoped SCC-use Role/RoleBinding in each respective `templates/scc-binding.yaml`; disable API-token automount, bind only the named release account to one existing SCC, and create no SCC, Namespace, ClusterRoleBinding, or global policy mutation.
- [X] T008 Add common contract fixtures to `block-storage-plain/tests/test_common_contract.py`, `block-storage-encrypted/tests/test_common_contract.py`, and `nfs-direct/tests/test_common_contract.py` for naming/selector collision resistance, debug-initdata selection and both override modes, reserved-metadata rejection, explicit image versions, default/explicit storage class, scoped privileges, and references remaining unowned; provide synthetic NFS inputs and opaque synthetic sealed test data without claiming live unsealing.
- [X] T009 Implement read-only live prerequisite diagnostics in `block-storage-plain/tests/check-prerequisites.sh`, `block-storage-encrypted/tests/check-prerequisites.sh`, and `nfs-direct/tests/check-prerequisites.sh` for runtime/namespace/initdata, release-account SCC use, raw-block `Delete` class/provider prerequisites where applicable, and guest/NFS connectivity where applicable; encrypted diagnostics must identify corrected sealed-mode trust as an external prerequisite linked to issue #153 without mutating it or fetching an additional KBS resource.

**Checkpoint**: Foundation ready. Charts have consistent strict values, release identity, and least-scope account/metadata contracts. Existing pattern resources are only referenced; default test/render work does not require upstream fixes or live hardware.

## Phase 3: User Story 5 — Observe Storage Persistence at Startup (Priority: P1)

**Goal**: Provide the same safe main-entrypoint state machine and explicit creation/existing/failure logs in every example before storage-specific Deployment integration.

**Independent Test**: Run each chart's startup fixtures against synthetic intended mounts: absent file becomes verified creation, an existing matching file is not rewritten, mismatch/access errors fail, and delayed/unavailable mounts cause no early/root-filesystem writes. The scripts are independently testable before any live Deployment; end-to-end checks are then consumed by each storage story.

### Tests for User Story 5

- [X] T010 [P] [US5] Author startup/file-state fixtures in `block-storage-plain/tests/test_startup.py`, `block-storage-encrypted/tests/test_startup.py`, and `nfs-direct/tests/test_startup.py` covering creation/readback, exact sentence plus terminal newline, existing-file non-recreation, mismatched/unreadable/nonregular/symlink files, failed creation/readback, no-clobber races, stable release-specific filenames, and explicit redacted log fields.
- [X] T011 [P] [US5] Author mount/readiness fixtures in `block-storage-plain/tests/test_storage_access.py`, `block-storage-encrypted/tests/test_storage_access.py`, and `nfs-direct/tests/test_storage_access.py` covering delayed visibility, false directory/marker readiness, source/filesystem mismatch, stale/reused helper PID and generation, individual-operation timeout, helper loss, and no demonstration-file access before verified main-container storage access.

### Implementation for User Story 5

- [X] T012 [P] [US5] Implement independent `block-storage-plain/scripts/log.sh`, `block-storage-encrypted/scripts/log.sh`, and `nfs-direct/scripts/log.sh` with escaped stable runtime events and truthful `created`/`verified` outcomes; log only the fixed public prose and nonsecret diagnostic metadata, never arbitrary file contents, key bytes, response bodies, or sealed tokens.
- [X] T013 [P] [US5] Implement independent `block-storage-plain/scripts/storage-access.sh`, `block-storage-encrypted/scripts/storage-access.sh`, and `nfs-direct/scripts/storage-access.sh` with bounded source/filesystem/access checks in the main container; support direct main-container mounts for plain/NFS and validated dynamic PID/generation plus helper mountinfo/proc-root access for encrypted storage, refusing fixed PIDs, helper-only markers, `eval`, or temporary-root fallback.
- [X] T014 [US5] Implement independent `block-storage-plain/scripts/prose-file.sh`, `block-storage-encrypted/scripts/prose-file.sh`, and `nfs-direct/scripts/prose-file.sh` to derive a stable namespace/chart/release-specific filename on the verified storage, create without clobbering only when absent, write and read back the fixed UTF-8 prose with one newline, preserve existing expected content, and fail explicitly without overwriting mismatched or unsafe files.
- [X] T015 [US5] Implement independent `block-storage-plain/scripts/main.sh`, `block-storage-encrypted/scripts/main.sh`, and `nfs-direct/scripts/main.sh` to emit storage waiting, enforce mount/access deadlines before invoking T014, emit exactly one successful file-result event, exit nonzero on failure, and only then execute the foreground application process; use a signal-aware long-running command available in the verified helper image, not an HTTP service or postStart race.
- [X] T016 [US5] Implement independent `block-storage-plain/scripts/readiness.sh`, `block-storage-encrypted/scripts/readiness.sh`, and `nfs-direct/scripts/readiness.sh` requiring initial file verification and current intended-storage access, invalidating stale helper generations and bounding checks so storage loss cannot leave an application falsely Ready.
- [X] T017 [US5] Package only each chart's own scripts in `block-storage-plain/templates/scripts-configmap.yaml`, `block-storage-encrypted/templates/scripts-configmap.yaml`, and `nfs-direct/templates/scripts-configmap.yaml`, with executable mounts and per-chart script checksums for pod-template rollout integration; no dependency on sibling files.
- [X] T018 [US5] Run the startup/access fixture suites through `block-storage-plain/tests/run.sh`, `block-storage-encrypted/tests/run.sh`, and `nfs-direct/tests/run.sh`, recording command results in `specs/001-add-storage-helm-examples/validation.md`; verify expected failures do not launch the application and produce no file on temporary storage, without describing fixture results as live mount/attestation evidence.

**Checkpoint**: The common startup safety feature is independently verified offline. Live mount/prose behavior is validated when each chart's storage-specific story is integrated; US5 full acceptance requires all three such live results.

## Phase 4: User Story 1 — Use Unencrypted Block Storage (Priority: P1) — MVP

**Goal**: Deploy plain raw-block/XFS storage with automatic pod replacement and destructive release-owned storage cleanup.

**Independent Test**: Install only `block-storage-plain`, observe verified file creation on intended XFS storage, delete its pod twice and observe existing expected prose from replacement pods on the same PVC/PV, then uninstall the disposable release and confirm provider-backed volume deletion.

### Tests for User Story 1

- [X] T019 [P] [US1] Author `block-storage-plain/tests/test_render.py` assertions for one-replica `Recreate` Deployment, chart-owned `Block`/`ReadWriteOnce` PVC, omitted default versus explicit storage class, separate formatting init/main device attachment, debug initdata, script mounts/probes, no key source, and no retention annotation or pod-owned claim.
- [X] T020 [P] [US1] Author `block-storage-plain/tests/test_format.py` fixtures for confirmed blank media, compatible XFS reuse, existing incompatible signatures, failed inspection, invalid device, mount-source mismatch, and reinitialization avoidance; destructive formatting must never occur on probe errors or known existing data.

### Implementation for User Story 1

- [X] T021 [P] [US1] Implement `block-storage-plain/templates/pvc.yaml` with stable release-isolated claim name, positive configurable capacity, fixed raw-block access mode, omitted class for null and explicit nonempty class otherwise; do not add keep policy or delete the claim on pod replacement.
- [X] T022 [P] [US1] Implement `block-storage-plain/scripts/format-storage.sh` using the official image's probe/XFS utilities: format only confirmed blank media without force flags, preserve recognized compatible XFS, and fail closed on unknown/incompatible signatures or inspection errors with nonsecret diagnostics.
- [X] T023 [US1] Implement `block-storage-plain/scripts/mount-storage.sh` to mount the same attached `/dev/block-device` as XFS inside the main container, validate existing mount source/device/filesystem, and connect that verified path to the US5 gate before prose operations; never write under an unmounted placeholder directory.
- [X] T024 [US1] Implement `block-storage-plain/templates/deployment.yaml` integrating the formatting init, main mount/startup scripts, one-replica `Recreate`, dedicated account, documented in-guest mounting privileges without host namespaces, image overrides, script checksum, and startup/readiness probes whose deadlines permit the configured gate and guest startup.
- [X] T025 [P] [US1] Implement `block-storage-plain/tests/verify-live.sh` with namespace/release/timeouts, storage-source and prose verification, recorded claim/PV identity, and `--expect-existing` checks that wait for new pod UIDs after deletion and prove no reformat/file recreation across two replacements.
- [X] T026 [P] [US1] Implement `block-storage-plain/tests/verify-uninstall.sh` requiring `--confirm-destructive`, capturing owned objects/PV/CSI volume handle before uninstall, waiting for their deletion, and requiring provider-specific backend deletion evidence; missing backend evidence or timeout is incomplete/failing, not passed, and no finalizers or unrelated resources are changed.
- [X] T027 [US1] Document independent install/configuration, version/image inventory, debug policy, required scoped permissions, raw-block/Delete prerequisites, prose outcomes, pod recovery, and irreversible Helm-uninstall cleanup in `block-storage-plain/README.md` and `block-storage-plain/templates/NOTES.txt`.
- [ ] T028 [US1] Validate `block-storage-plain/tests/run.sh` and, only on an explicitly approved disposable supported environment, `tests/verify-live.sh` plus `tests/verify-uninstall.sh`; record separate offline/live/backend evidence or explicit environment blockers in `specs/001-add-storage-helm-examples/validation.md`.

**Checkpoint**: A viable safe plain-block MVP exists with the US5 startup safety already integrated. No Trustee key resource or NFS server is needed for this release.

## Phase 5: User Story 2 — Use Encrypted Block Storage (Priority: P1)

**Goal**: Encrypt, reopen, and expose raw-block/XFS data using exactly one selected key-delivery mode, without fallback or destructive reformatting.

**Independent Test**: Install only `block-storage-encrypted`, verify LUKS and prose-file access, replace its pod twice using the same PVC/key, and validate uninstall. Repeat for curl/sealed/insecureSecret; denied/empty/wrong keys and tampered signed tokens fail closed. Sealed live acceptance requires corrected upstream debug initdata; never mark it passed based on an issue or offline mock.

### Tests for User Story 2

- [X] T029 [P] [US2] Author `block-storage-encrypted/tests/test_render.py` for the key-mode enum, conflicting/missing sources, true sealed-envelope versus existing-envelope Secret, insecure existing Secret only, one raw-block claim, shared PID/native sidecar ordering, memory-backed key/control staging, no plaintext key values, scoped privileges, and images/initdata overrides.
- [X] T030 [P] [US2] Author `block-storage-encrypted/tests/test_key_delivery.py` fixtures for exact local-CDH resource-only retrieval, loopback proxy bypass, HTTP/timeout/empty/error handling, bounded single-line ASCII key validation, newline/NUL rejection, still-sealed token rejection, no fallback, and no key/response/token exposure in logs or command arguments; distinguish offline token fixtures from actual Kata/CDH unsealing.
- [X] T031 [P] [US2] Author `block-storage-encrypted/tests/test_encrypted_storage.py` fixtures for existing LUKS/XFS reuse, wrong key including an already-open mapper, incorrect mapper backing device, failed probes, unexpected signatures, stale mount/PID generation, and no formatting on any recognized existing data or inspection failure.

### Implementation for User Story 2

- [X] T032 [US2] Extend `block-storage-encrypted/values.schema.json` and `block-storage-encrypted/templates/_helpers.tpl` for the three mutually exclusive modes and their required sources, require one genuine `sealed.` source in sealed mode without decoding secret payloads into logs, and implement `templates/sealed-secret.yaml` containing only an operator-supplied envelope when chart-owned; reference existing Secrets without ownership and expose no signature-bypass value.
- [X] T033 [P] [US2] Implement `block-storage-encrypted/scripts/fetch-key.sh` with finite `curl --fail --silent --show-error` local-CDH retrieval of only the configured resource, restrictive memory-backed staging permissions and cleanup, byte-level passphrase validation, and builtin variable/stdin handling without shell tracing, `eval`, expanded-key arguments, stdout secrets, or public-package installation.
- [X] T034 [US2] Implement `block-storage-encrypted/scripts/encrypted-storage.sh` as a fail-closed chart-local state machine using Red Hat cryptsetup/XFS tools: validate selected key and device signatures, validate existing-key access even with an open mapper, check mapper backing device, format only blank raw/mapped media, mount/verify source, publish current PID/generation after success, and handle stop/restart cleanup without invoking the stock helper's unsafe probe-error format fallback.
- [X] T035 [US2] Implement `block-storage-encrypted/templates/pvc.yaml` and `templates/deployment.yaml` with stable owned raw-block claim, one-replica `Recreate`, curl-only retrieval init, Secret-backed `PASS` for Kata/CDH sealed unsealing or explicit insecure mode, native encryption sidecar, memory-backed control/key volumes, shared process namespace, main proc-root access gate/prose checks, image overrides and source-aware startup/readiness probes; no postStart gate or fixed helper PID.
- [X] T036 [P] [US2] Implement `block-storage-encrypted/tests/verify-live.sh` for mode-specific prerequisites, exact one-resource key reference, LUKS and intended mount proof, creation/existing logs, same-claim replacement, denied/wrong/empty key and tampered-token failures, and helper restart readiness; report sealed trust unavailable as blocked and never modify upstream initdata or add resources.
- [X] T037 [P] [US2] Implement `block-storage-encrypted/tests/verify-uninstall.sh` with explicit destructive confirmation, owned-envelope-versus-external-key ownership checks, PV/backend deletion evidence, and preservation of Trustee/debug initdata/operator-supplied Secrets; no cross-chart test-runtime dependency.
- [X] T038 [US2] Document all three modes, externally generated real signed-token transport, one encryption resource, guest-local verification-key/corrected-initdata prerequisite and issue #153, measured-initdata/pod update consequences, helper utility safety choice, environment/shared-PID/debug-policy residual exposure, image overrides and destructive cleanup in `block-storage-encrypted/README.md` and `templates/NOTES.txt`; include no plaintext passphrase or private JWK examples.
- [X] T039 [US2] Run `block-storage-encrypted/tests/run.sh`, ShellCheck and redaction/static unsafe-operation checks, recording precise offline results and image inventory findings in `specs/001-add-storage-helm-examples/validation.md` before attempting any live encrypted storage.
- [ ] T040 [US2] On an explicitly approved disposable environment, exercise curl and insecure modes and, when corrected upstream trust is genuinely provisioned, sealed mode through `block-storage-encrypted/tests/verify-live.sh` and `tests/verify-uninstall.sh`; record separate outcomes for every mode and negative scenario in `specs/001-add-storage-helm-examples/validation.md`, leaving unavailable sealed/backend checks unresolved rather than relaxing verification.

**Checkpoint**: The encrypted chart is independently implemented and offline-tested. Full US2 acceptance remains contingent on evidenced live tests for all three modes; upstream trust is an external prerequisite, not a reason to stop coding or fabricate success.

## Phase 6: User Story 3 — Mount an Existing NFS Export Directly (Priority: P2)

**Goal**: Demonstrate direct main-container NFS mounting and replacement persistence without any Kubernetes persistent-volume interface.

**Independent Test**: Install only `nfs-direct` against a writable disposable existing export, confirm NFS source/type and creation/existing prose logs across two pod replacements, then uninstall chart objects while the server/export/files remain intact. Unavailable mounts and permission failures never launch a ready application or create fallback files.

### Tests for User Story 3

- [X] T041 [P] [US3] Author `nfs-direct/tests/test_render.py` for required server/export/options and path validation, no PV/PVC/Kubernetes NFS volume, no shared PID namespace/extra mount sidecar, single main-container Deployment, debug initdata, image overrides, and isolated metadata/accounts.
- [X] T042 [P] [US3] Author `nfs-direct/tests/test_nfs_mount.py` fixtures for hostname/IPv4/bracketed IPv6 source construction, option argument quoting without shell evaluation, exact NFS source/type checks, delayed/unreachable mount deadlines, hard-mount operation supervision, root-squash/read-only failures, and no prose operations before mount verification.

### Implementation for User Story 3

- [X] T043 [US3] Complete `nfs-direct/values.schema.json` and `templates/_helpers.tpl` with required nonempty validated server, absolute export, bounded validated mount-option list, normalized application path, and a stable namespace/chart/release-specific prose-file identity distinct on a shared export.
- [X] T044 [US3] Implement `nfs-direct/scripts/mount-storage.sh` to assert `mount.nfs` availability, mount the existing export directly in the main container using quoted arguments and default NFSv4.1/hard options, bound supervision, verify source/type/access before US5 file checks, and use signal-aware best-effort unmount without server/export deletion.
- [X] T045 [US3] Implement `nfs-direct/templates/deployment.yaml` with one-replica `Recreate`, release account, documented in-guest mount privileges, main direct-mount/startup/prose entrypoint and current-source readiness, image overrides and guest resources; render no PVC/PV, Kubernetes NFS volume, host namespaces, or bidirectional mount propagation.
- [X] T046 [P] [US3] Implement `nfs-direct/tests/verify-live.sh` and `tests/verify-uninstall.sh` for export access/source proof, file persistence across new pod UIDs, timeout/permission failures, explicit uninstall confirmation and owned-object cleanup with external NFS data preserved; use only this chart's local scripts.
- [X] T047 [US3] Document independent NFS inputs, guest-kernel/client/network prerequisites, export identity/root-squash handling, hard-mount timeout limitations, absent-versus-existing prose outcomes, no confidentiality claim for NFS transport/server data, image overrides and external-export retention in `nfs-direct/README.md` and `templates/NOTES.txt`.
- [ ] T048 [US3] Validate `nfs-direct/tests/run.sh` and, on an explicitly approved disposable export, two-replacement/source/negative/uninstall scenarios through the local live scripts; record live or blocked outcomes in `specs/001-add-storage-helm-examples/validation.md` and complete US5's third-example live evidence only if actually observed.

**Checkpoint**: Direct NFS is independently usable without block-storage or Trustee-key dependencies. The external export and its data are never chart-owned artifacts.

## Phase 7: User Story 4 — Configure and Run Examples Together (Priority: P2)

**Goal**: Prove consistent overrides, independent use, namespace coexistence, disconnected operation and discoverability.

**Independent Test**: Render and deploy all three plus another release in one namespace, verify default/alternate/inline/cluster-default initdata and every image-role override, prove no selector/name/file collisions, and remove one release without affecting others. Follow each chart's README without reading a sibling.

### Tests for User Story 4

- [X] T049 [P] [US4] Add self-contained isolation test cases in `block-storage-plain/tests/test_isolation.py`, `block-storage-encrypted/tests/test_isolation.py`, and `nfs-direct/tests/test_isolation.py` for short/long similar release names, namespace/chart identity, references/selectors, externally supplied resource ownership, and stable distinct NFS filenames; include local standalone package checks proving no sibling file/runtime dependency.
- [X] T050 [P] [US4] Add self-contained override/disconnected test cases in `block-storage-plain/tests/test_overrides.py`, `block-storage-encrypted/tests/test_overrides.py`, and `nfs-direct/tests/test_overrides.py` for alternate ConfigMap, inline precedence, cluster-default skip label, labels/annotations and protected metadata, each consumed full-reference image override, policy/secret/resource overrides, and renders containing no public source registry after mirror overrides.

### Implementation for User Story 4

- [X] T051 [US4] Add `block-storage-plain/tests/fixtures/mirror-values.yaml`, `block-storage-encrypted/tests/fixtures/mirror-values.yaml`, and `nfs-direct/tests/fixtures/mirror-values.yaml`, plus each respective `tests/fixtures/initdata-values.yaml`, using synthetic nonsecret inputs; reconcile defaults/schemas/helper render behavior against the complete values contract without introducing a shared library chart or changing external pattern resources.
- [X] T052 [US4] Add standalone coexistence/override modes to `block-storage-plain/tests/verify-live.sh`, `block-storage-encrypted/tests/verify-live.sh`, and `nfs-direct/tests/verify-live.sh` for new pod UIDs, actual admitted initdata selection and shared-namespace release isolation; document prerequisites and require explicit disposable targets rather than auto-provisioning namespaces, NFS servers, trust anchors, or extra Trustee resources.
- [X] T053 [US4] Create root `README.md` with three short linked example descriptions, storage/security differences, corrected-initdata issue linkage, common prepared-cluster prerequisites, and warnings that block Helm uninstall deletes owned backing storage while external NFS data remains.
- [X] T054 [US4] Reconcile `block-storage-plain/README.md`, `block-storage-encrypted/README.md`, and `nfs-direct/README.md` with consistent option naming, complete role-image inventories, mirrored-registry/guest CA/auth/proxy and attestation prerequisites, initial/retained-file logs, narrowly scoped permissions and full independent deployment/cleanup instructions; justify any non-Red Hat runtime dependency if one became necessary.
- [X] T055 [US4] Run all chart-local isolation/override fixtures via their `tests/run.sh` entrypoints and compare a collection of synthetic renders for cross-chart resource/selector collisions, recording offline evidence in `specs/001-add-storage-helm-examples/validation.md` without presenting it as live namespace coexistence.
- [ ] T056 [US4] Execute the approved live coexistence, second-release, one-release removal and disconnected scenarios from `specs/001-add-storage-helm-examples/quickstart.md` using each chart's local scripts; record all three-plus-second release outcomes, unaffected remaining workloads, actual guest mirror references, and explicitly unavailable cases in `specs/001-add-storage-helm-examples/validation.md`.

**Checkpoint**: Users can discover and independently configure the examples. Full disconnected/coexistence acceptance requires recorded live results rather than successful templates alone.

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Complete repository delivery controls and review all requirement/acceptance evidence.

- [X] T057 Implement `.github/workflows/validate-examples.yml` with pinned action/tool/dependency versions and a per-chart matrix running Helm lint/schema/render tests, ShellCheck/startup fixtures, chart/image-version checks, no-build/no-runtime-package-manager assertions and independence checks; do not put secrets or live-hardware jobs into untrusted pull-request execution or claim public CI validates attestation.
- [X] T058 Review every chart's `scripts/`, `templates/`, `values.yaml`, and `values.schema.json` for injection/path/symlink safety, key/token redaction, current mount identity, no force-format/probe-error fallback, stale-helper readiness, namespace-only SCC authorization, immutable selectors and uninstall ownership; record actionable review findings and their resolution in `specs/001-add-storage-helm-examples/validation.md`.
- [X] T059 Verify chart metadata/image references and per-chart standalone package contents in `block-storage-plain/Chart.yaml`, `block-storage-encrypted/Chart.yaml`, and `nfs-direct/Chart.yaml`, with schema/README/NOTES consistency, explicit maintained versions and no accidental dependency on `staging/` or sibling examples; update `specs/001-add-storage-helm-examples/validation.md` with actual findings.
- [X] T060 Reconcile `specs/001-add-storage-helm-examples/quickstart.md` with implemented runner flags, file paths, probe/deadline semantics and actual logs; map FR-001–FR-027 and SC-001–SC-012 to concrete offline/live evidence in `validation.md`, explicitly retaining any unfulfilled upstream sealed-mode or backend-deletion gates.
- [X] T061 Run final repository-relevant validation and chart-local `tests/run.sh` suites, inspect changes for unintended staged-sample modifications or secret material, and record final outcomes in `specs/001-add-storage-helm-examples/validation.md`; leave live tests unpassed where credentials/hardware/corrected initdata/provider evidence are absent and do not commit, push, deploy, or delete additional resources without explicit authorization.

**Checkpoint**: Deliverable charts, documentation and CI are complete only when applicable validation passes; full feature acceptance additionally requires all specified live outcomes, including sealed mode against corrected upstream trust and actual backing-volume deletion.

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1 Setup (T001–T003)
        ↓
Phase 2 Foundation (T004–T009)
        ↓
US5 Startup safety (T010–T018)
        ├── US1 Plain block (T019–T028) ──────┐
        ├── US2 Encrypted block (T029–T040) ──┼── US4 Collection/overrides (T049–T056)
        └── US3 Direct NFS (T041–T048) ───────┘                  ↓
                                                    Polish (T057–T061)
```

- Complete Setup and Foundation before story work. For an MVP, T003 verifies only the plain-chart roles; encrypted/NFS role findings remain required before those runtime paths are released.
- US5 fixture-tested startup safety precedes storage integration. US1/US2/US3 are then independent packages and can be implemented in parallel without sibling dependencies; written phase order presents P1 stories before P2.
- US5 live acceptance is collected incrementally by T028/T040/T048; completing fixtures does not assert that all three live stories already passed.
- US4 whole-collection acceptance follows all three storage stories; its test-authoring tasks can run after Foundation while runtime integration waits for the story scripts/charts.
- Upstream issue #153 does not block offline implementation or task generation. Corrected initdata/guest trust **does** block sealed live acceptance in T036/T040 and the final full-feature signoff.
- Destructive/live tasks require a separately approved disposable environment and targets. If none is available, implement the scripts and record validation blocked; do not execute them against an inferred current context.

### Within each story

1. Author the listed offline test cases first and demonstrate relevant missing implementation is detected.
2. Complete independent files marked `[P]` only once prerequisites they read/import exist.
3. Integrate templates after scripts/resources are ready; do not let mount/file operations race the gate.
4. Run fixture/render validation before approved live verification.
5. Record live, blocked, and offline outcomes separately; never turn a missing prerequisite into an insecure workaround or a checked acceptance claim.

### Parallel opportunities

- US5: T010/T011 test authoring; then T012/T013 independent logging/access scripts; T014–T017 integrate sequentially.
- US1: T019/T020 tests; T021 PVC and T022 formatter after test authoring; T025 live verifier and T026 uninstall verifier after chart integration.
- US2: T029/T030/T031 tests; T033 key-fetch script can be developed separately from mode templates once source contracts are fixed; T036/T037 verifiers after integration.
- US3: T041/T042 tests; T046 verifier development can proceed alongside T047 documentation after the runtime/CLI contracts are implemented, provided files do not overlap.
- US4: T049/T050 tests after Foundation; documentation and verification jobs must not write another active task's files concurrently.
- Cross-story: after T018, separate workers can implement US1/US2/US3 because their files are disjoint. Serialize writes to `validation.md` and shared root/CI artifacts.

## Parallel Example: User Story 5

```text
T010: Author per-chart startup/file-state tests in tests/test_startup.py.
T011: Author per-chart mount/readiness tests in tests/test_storage_access.py.
After test contracts exist:
T012: Implement per-chart scripts/log.sh.
T013: Implement per-chart scripts/storage-access.sh.
```

## Parallel Example: User Story 1

```text
T019: Write block-storage-plain/tests/test_render.py.
T020: Write block-storage-plain/tests/test_format.py.
After test authoring:
T021: Implement block-storage-plain/templates/pvc.yaml.
T022: Implement block-storage-plain/scripts/format-storage.sh.
```

## Parallel Example: User Story 2

```text
T029: Write block-storage-encrypted/tests/test_render.py.
T030: Write block-storage-encrypted/tests/test_key_delivery.py.
T031: Write block-storage-encrypted/tests/test_encrypted_storage.py.
After chart integration:
T036: Implement block-storage-encrypted/tests/verify-live.sh.
T037: Implement block-storage-encrypted/tests/verify-uninstall.sh.
```

## Parallel Example: User Story 3

```text
T041: Write nfs-direct/tests/test_render.py.
T042: Write nfs-direct/tests/test_nfs_mount.py.
After runtime/CLI integration:
T046: Implement nfs-direct/tests/verify-live.sh and tests/verify-uninstall.sh.
T047: Document nfs-direct/README.md and templates/NOTES.txt.
```

## Parallel Example: User Story 4

```text
T049: Write per-chart tests/test_isolation.py.
T050: Write per-chart tests/test_overrides.py.
```

## Implementation Strategy

### MVP first

Complete Setup/Foundation, US5 startup safety, and US1 plain block. This is the smallest safe demonstration: no key service or NFS export, automatic prose creation and persistence logs, same-volume replacement and explicit destructive uninstall. Validate offline immediately; validate live only when a disposable supported environment is supplied. US5's full three-example live acceptance is not part of that first MVP claim.

### Incremental delivery

1. Establish configuration/naming/image checks and independently tested startup safety.
2. Deliver the plain-block MVP with its independent README and verification tools.
3. Deliver the encrypted chart's three modes without waiting to code on upstream changes; gate sealed **live success** on the corrected-initdata prerequisite rather than bypassing it.
4. Deliver direct NFS with no persistent-volume interface and no deletion of external export data.
5. Prove collection coexistence, consistent overrides, disconnected startup and root README discovery.
6. Complete CI/review/traceability and live signoff only where actual evidence is available.

### Parallel team strategy

After Foundation and US5, independent workers may implement the three chart directories. Assign one coordinator for shared `validation.md`, root README, and CI integration. Avoid concurrent edits within a chart's helpers/schema/Deployment; no delegation is required by this task list.

## Coverage and Counts

| Group | Tasks | Count |
|---|---|---:|
| Setup | T001–T003 | 3 |
| Foundation | T004–T009 | 6 |
| US5 startup persistence (P1) | T010–T018 | 9 |
| US1 plain block (P1) | T019–T028 | 10 |
| US2 encrypted block (P1) | T029–T040 | 12 |
| US3 direct NFS (P2) | T041–T048 | 8 |
| US4 configuration/coexistence (P2) | T049–T056 | 8 |
| Polish | T057–T061 | 5 |
| **Total** | **T001–T061** | **61** |

| Requirement group | Tasks providing implementation or acceptance evidence |
|---|---|
| FR-001–FR-006 | T001, T004–T009, T049–T054 |
| FR-007–FR-010 | T019–T028, T031, T034–T040 |
| FR-011–FR-013 | T029–T040 |
| FR-014–FR-017 | T003–T005, T041–T048, T050–T056 |
| FR-018–FR-022 | T007–T009, T016, T024–T028, T035–T040, T045–T048, T053–T061 |
| FR-023–FR-026 | T010–T018, T023–T028, T034–T040, T042–T048 |
| FR-027 | T009, T032, T036, T038, T040, T053, T060–T061 |
| SC-001–SC-012 | Per-story live checks T028/T040/T048, collection validation T055–T056, and final evidence reconciliation T060–T061 |

## Notes

- All tasks remain unchecked until actually completed; authoring this list is not implementation/test completion.
- Each chart must be installable and understandable without its siblings. Repeated small scripts/contracts are intentional; keep behavior aligned through tests rather than shared deployment files.
- Corrected upstream debug initdata is assumed for design, not claimed to exist. A missing signature-verification prerequisite must remain a visible live acceptance blocker.
- No step authorizes production data destruction, cluster-wide privilege grants, extra Trustee resources, runtime package installation, image builds in this repository, or silently weakened token verification.
- Do not commit/push automatically or overwrite untracked user samples. Keep actual findings and unmet acceptance gates explicit.

## Phase 9: Convergence

**Assessment**: Present-state review against `spec.md`, `plan.md`, existing T001–T061 and constitution principles I–VI. Checked 27 functional requirements, 12 buildable success criteria, 27 acceptance scenarios and 12 plan decisions. No observed constitution MUST violation; findings F1–F8 are HIGH and F9–F11 are MEDIUM. This section is append-only: existing task states and descriptions remain authoritative and unchanged.

**Execution boundaries**: Convergence itself changed no code, specification, plan, or existing task. Implement the buildable fixes below without inferring permission for cluster deployments, pod deletion, Trustee changes, or backend deletion. T069 remains gated on explicitly approved disposable targets and corrected upstream sealed trust; reuse resulting evidence to close the original live tasks rather than running duplicate destructive tests. Keep chart-local implementations independent. Serialize tasks that touch the same runtime scripts, templates, schemas or verification modules; validate code fixes before live acceptance.

- [X] T062 [F1 HIGH] Pin the validated storage directory/view before prose operations in `block-storage-plain/scripts/prose-file.sh`, `block-storage-encrypted/scripts/prose-file.sh` and `nfs-direct/scripts/prose-file.sh`, coordinate their `scripts/storage-access.sh` and `scripts/main.sh` gates as needed, and operate against that pinned intended filesystem rather than a subsequently re-resolved absolute path; add deterministic regression cases in each `tests/test_startup.py` that remove/replace the mount or path between verification and file open, proving no temporary-root file, overwritten existing data, false creation-success log or Ready application per FR-023, FR-024, SC-010 and US5/AC4–AC5 (contradicts).
- [ ] T063 [F2 HIGH] Provide a complete policy-compatible readiness and storage/prose verification path in all three `templates/deployment.yaml`, `scripts/readiness.sh` and `tests/live.py` implementations that works when the selected initdata denies interactive exec, without silently relaxing default or operator policy, weakening main-container storage evidence, or treating logs-only diagnostics as full acceptance; add appropriate fixtures and standalone README guidance for the supported policy path per FR-005, FR-018, FR-021, T052 and the restrictive-initdata edge case (partial).
- [X] T064 [F3 HIGH] Make cleanup in `block-storage-plain/tests/live.py`, `block-storage-encrypted/tests/live.py` and `nfs-direct/tests/live.py` honor the configured end-to-end deadline rather than the fixed 60-second subprocess cap, poll provider-specific backend absence until success/deadline with explicitly distinguished pending/error results, and test slow Helm teardown, delayed PV removal and backend deletion finishing after PV disappearance; never strip finalizers, change global reclamation or claim unobserved deletion per FR-019, SC-005, T026, T037 and plan: three-level uninstall verification (partial).
- [X] T065 [F4 HIGH] Capture an explicit release-owned inventory and the identities of referenced external resources before uninstall in each chart's `tests/live.py`, distinguish Helm/controller ownership from shared application labels, wait only for owned objects, and verify referenced initdata/key/pull resources remain unchanged afterward; add mocked API/Helm regressions in each `tests/test_live_cli.py` (or chart-local cleanup test module) including externally managed objects carrying matching application labels and owned versus referenced envelope Secrets, with no deletion of NFS export/data or external infrastructure per FR-008, FR-019, T026 and T037 (partial).
- [X] T066 [F5 HIGH] Extend `block-storage-encrypted/tests/test_encrypted_storage.py`, `tests/test_helper_identity.py` and readiness/startup fixtures to exercise successful blank-device initialization, existing LUKS/XFS reuse, correct-key reuse of an already-open mapper, wrong backing-device/mount-source rejection, errors after mapper creation, and helper stop/restart invalidating stale main readiness; assert command ordering, absence of destructive reformatting on reuse/error, and PID/generation publication only after verified mounting rather than stopping every encrypted fixture before the success path per FR-010, FR-018, FR-021, T011, T031 and T036 (partial).
- [X] T067 [F6 HIGH] Extend `nfs-direct/tests/test_nfs_mount.py`, `tests/test_storage_access.py` and startup/readiness fixtures to run actual NFS-kind verification rather than an always-successful storage-check stub or plain/XFS mode, covering exact NFS source/type mismatches, delayed/unreachable mounts, bounded mount/file-operation supervision, root-squash/read-only creation denial, retained expected files on read-only exports, and no file operation/application start before intended mount access; use safe mocked interfaces and a supported timeout implementation without contacting or modifying an inferred live export per FR-014, FR-018, FR-026, SC-010–SC-011, T011 and T042 (partial).
- [X] T068 [F7 HIGH] Implement the planned opt-in collection/coexistence and override/disconnected verification capabilities in each chart's `tests/live.py` and `tests/verify-live.sh` (or independent chart-local orchestration scripts): require explicit approved release/context/namespace and expected-mirror inputs, check three examples plus a second release for owned-resource/reference/selector/file isolation, verify every consumed admitted-pod image uses the supplied mirror and selected initdata mode, and confirm remaining releases still verify after an explicitly authorized one-release removal; add mocked API cases and update standalone usage documentation without introducing sibling runtime dependencies per FR-008, FR-017, FR-021, SC-002, SC-006–SC-007 and T052 (partial).
- [ ] T069 [F8 HIGH] After code fixes and only once an explicitly approved disposable OpenShift context/namespace, compatible raw-block Delete provider with backend evidence adapter, writable test NFS export, single Trustee encryption resource and corrected sealed-token trust are supplied, complete the remaining T028, T040, T048 and T056 scenarios through the chart-local live tools and record actual source-verified file creation, two new-pod replacements with unchanged data/claim identities, all three key modes and denied/tampered cases, propagated-mount/timeout failures, coexistence/disconnected outcomes and actual backing-volume deletion in `specs/001-add-storage-helm-examples/validation.md`; preserve external resources and leave unavailable outcomes explicitly blocked rather than fabricating success or bypassing verification per SC-001–SC-007, SC-009–SC-012, FR-027 and T028/T040/T048/T056 (partial).
- [X] T070 [F9 MEDIUM] Enforce safe override invariants in all three `values.schema.json` and `templates/_helpers.tpl` implementations: reject system mount targets such as `/usr` and its descendants before deployment, require complete CPU/memory requests/limits and budgets compatible with the fixed guest RAM/overhead (or a coherent supported sizing override), and reject known floating aliases such as `nightly` while retaining valid maintained mirror/digest references; add negative render fixtures in each `tests/test_common_contract.py` and `tests/test_overrides.py` for the currently accepted unsafe/incomplete values per T004, T005, FR-006, FR-015 and plan: strict values/guest-memory constraints (partial).
- [X] T071 [F10 MEDIUM] Complete stage-specific failure logging across each chart's `scripts/log.sh`, `scripts/main.sh` and `scripts/prose-file.sh`: report the full demonstration file path for file failures, distinguish mount path from file path, explicitly report file-check-not-run on outer mount/propagation timeout, include the configured deadline, preserve truthful created/unknown status, and test every early/outer timeout and read/write/mismatch path without emitting key, token or arbitrary file contents; ensure timeout reporting meets the stated configured-deadline outcome rather than silently relying on later cleanup/grace per FR-023, FR-025, SC-010–SC-011, US5/AC3–AC5 and T012/T015 (partial).
- [X] T072 [F11 MEDIUM] Apply supported `resourceAnnotations` consistently to optional SCC Roles and RoleBindings in `block-storage-plain/templates/scc-binding.yaml`, `block-storage-encrypted/templates/scc-binding.yaml` and `nfs-direct/templates/scc-binding.yaml`, preserving reserved ownership/identity guards; extend each `tests/test_common_contract.py` to verify custom annotations across all chart-owned object kinds with scoped SCC binding enabled per FR-006 and T006 (partial).

**Handoff**: Implement buildable HIGH fixes first, extend their tests before the corresponding changes, then complete MEDIUM configuration/diagnostic consistency work. T069 is the final externally gated acceptance step even though it is listed with the HIGH findings. A follow-up `/speckit.converge` must assess the resulting current code and evidence; the pre-existing checked tasks above were not rewritten by this review.

## Phase 10: Convergence

**Present-state assessment**: Checked 27 functional requirements, 12 success criteria, 27 acceptance scenarios, 12 plan decisions, 72 existing tasks and constitution principles I–VI. Remaining findings C10-F1–C10-F8 are HIGH and C10-F9–C10-F11 are MEDIUM: one contradicts gap and ten partial gaps. No observed constitution MUST violation or unrequested runtime addition. This assessment reads current artifacts/code, not branches, diffs or history.

**Scope and handoff**: These tasks narrow the remaining scope of T062–T072; they do not replace, renumber, rewrite or complete those tasks. Reuse code and validation evidence to close linked tasks rather than repeating work or destructive tests. Runtime delivery remains Helm charts, Red Hat images and embedded shell scripts. Python may remain in chart-local development/verification tooling excluded from deployed charts, but do not reintroduce a runtime Python service or expand into another application stack. Live work is still gated on explicit approved targets; registry authentication is not cluster-operation authorization.

- [X] T073 [C10-F1 HIGH] Complete T062's storage-view pinning in `block-storage-encrypted/scripts/prose-file.sh` and `nfs-direct/scripts/prose-file.sh`, which still open files through a re-resolved absolute path after checking the mount; apply independently packaged Helm/shell logic consistent with the current `block-storage-plain/scripts/prose-file.sh`, add the deterministic path/mount-replacement regressions to each chart's `tests/test_startup.py`, and validate the plain implementation and all three readiness/startup paths before closing T062 per FR-023, FR-024, SC-010 and US5/AC4–AC5 (contradicts).
- [ ] T074 [C10-F2 HIGH] Resolve T063's remaining exec-denying-policy compatibility in all three `templates/deployment.yaml`, `scripts/readiness.sh`, `tests/live.py` and standalone READMEs using supported Helm/shell probe and policy mechanisms from the existing Red Hat stack; retain default debug initdata, full main-container storage/prose evidence and explicit overrides without weakening selected policy or adding runtime Python/web services. If the stated verification requirement cannot be met within that runtime scope, retain an explicit blocker and request a narrowly scoped requirement decision rather than silently weakening acceptance or adding another stack per FR-005, FR-018, FR-021, T063 and the restrictive-initdata edge case (partial).
- [X] T075 [C10-F3 HIGH] Complete T064's deadline-aware cleanup in `block-storage-encrypted/tests/live.py` and `nfs-direct/tests/live.py` using their own chart-local helpers, preserving the shared end-to-end deadline and bounded polling already present in `block-storage-plain/tests/live_support.py`; add integration regressions for slow Helm teardown, delayed PV/backend disappearance, adapter pending/error codes and deadline exhaustion across all three `tests/test_cleanup_support.py` or equivalent local modules, and reconcile backend-adapter usage in each README before closing T064 per FR-019, SC-005, T026, T037 and plan: three-level cleanup verification (partial).
- [X] T076 [C10-F4 HIGH] Complete T065's ownership and external-resource preservation integration in the encrypted and NFS charts' `tests/live.py` with independent local support files; validate the plain implementation through full mocked API/Helm teardown flows, including externally managed objects carrying matching application labels, Deployment/ReplicaSet/Pod ownership, chart-owned versus referenced envelope Secrets and unchanged referenced-resource identities/content. Never adopt or delete an external object merely because of its labels, and preserve external NFS data per FR-008, FR-019, T065 and T037 (partial).
- [X] T077 [C10-F5 HIGH] Complete T066's missing positive and recovery/error-path fixtures in `block-storage-encrypted/tests/test_encrypted_storage.py`, `tests/test_helper_identity.py` and startup/readiness tests: exercise successful blank initialization, existing LUKS/XFS reopen without reformat, correct-key mapper reuse, wrong backing/mount identity, failures after mapper creation and helper restart invalidation, with assertions on mutation ordering and publication only after verified mount. The current four rejection-only cases do not satisfy this state-machine coverage per FR-010, FR-018, FR-021, T031 and T066 (partial).
- [X] T078 [C10-F6 HIGH] Complete T067 in `nfs-direct/tests/test_nfs_mount.py`, `tests/test_storage_access.py` and startup/readiness tests by exercising the real NFS-kind storage checker rather than an unconditional-success stub; cover wrong source/type, delayed/unreachable mounts, bounded operation supervision, read-only/root-squash write failure and retained expected prose, and prove no file operation or Ready application before correct main-container access without contacting an inferred live server per FR-014, FR-018, FR-026, SC-010–SC-011 and T067 (partial).
- [X] T079 [C10-F7 HIGH] Complete T068's planned collection/coexistence and disconnected assertions in the chart-local `tests/live.py`, `tests/verify-live.sh` and their test modules: accept explicit approved release/context/namespace and expected-mirror inputs, check all three examples plus a second release for selection/reference/file isolation, validate consumed admitted-pod image references and selected initdata, and verify remaining releases after an explicitly authorized removal; document standalone invocation and avoid sibling runtime dependencies per FR-008, FR-017, FR-021, SC-002, SC-006–SC-007, T052 and T068 (partial).
- [ ] T080 [C10-F8 HIGH] Complete the still-gated T028, T040, T048, T056 and T069 acceptance only after the explicitly approved disposable cluster/namespace/export, compatible Delete provider and backend evidence adapter, single encryption resource and corrected upstream sealed trust exist. Record actual guest source/file verification, two pod replacements, all three key modes and negative cases, mount-timeout/propagation behavior, coexistence/disconnected operation and backend deletion in `specs/001-add-storage-helm-examples/validation.md`; use one evidence set to close linked tasks and retain unavailable outcomes as blocked, not successful per SC-001–SC-007, SC-009–SC-012, FR-027 and T069 (partial).
- [X] T081 [C10-F9 MEDIUM] Complete T070's unsafe-override rejection in each chart's `values.schema.json`, `templates/_helpers.tpl`, `tests/test_common_contract.py` and `tests/test_overrides.py`: current read-only renders accept `/usr`, a deleted application memory limit and `:nightly`. Reject system mount targets, require coherent CPU/memory budgets for fixed guest RAM/overhead and reject known floating aliases while preserving supported maintained mirror/digest overrides per T004, T005, FR-006, FR-015 and T070 (partial).
- [X] T082 [C10-F10 MEDIUM] Complete T071 across all three charts' `scripts/log.sh`, `scripts/main.sh` and `scripts/prose-file.sh`, including the plain chart's pinned-view error paths: distinguish full demonstration-file versus mount paths, include configured deadline and explicit not-run file-check status on outer timeout, and preserve truthful created/unknown outcomes without key/token/arbitrary-content exposure. Add early/outer-timeout and file-error assertions and reconcile the standalone log guidance per FR-023, FR-025, SC-010–SC-011, US5/AC3–AC5 and T071 (partial).
- [X] T083 [C10-F11 MEDIUM] Complete T072's `resourceAnnotations` propagation in all three `templates/scc-binding.yaml` files, retaining reserved ownership/identity checks; add a chart-local test that enables SCC binding and verifies annotations on every owned object kind, since Roles and RoleBindings currently omit the accepted annotation value per FR-006, T006 and T072 (partial).

**Next execution order**: Finish the remaining cross-chart safety/cleanup implementation and its regression tests, resolve policy compatibility within the stated Helm/shell runtime boundary, then complete validation/diagnostic consistency. T080 is the final externally gated evidence step despite its HIGH severity. Preserve every existing task state during this convergence pass; `/speckit.implement` is responsible for code changes and completion tracking, followed by another current-state convergence review.

## Phase 11: Convergence

**Assessment — 2026-10-09**: Current-state review checked 27 functional requirements, 12 buildable success criteria, 27 acceptance scenarios, 12 plan decisions, 83 existing tasks and constitution principles I–VI. Findings R1–R8 are HIGH; R9–R11 are MEDIUM. One gap contradicts intent and ten are partial. No observed constitution MUST violation or unrequested runtime addition. Existing task descriptions/states remain unchanged.

**Boundaries**: Complete the linked residual work rather than repeat already implemented plain-chart foundations. Keep runtime delivery to Helm, Red Hat images and embedded shell; Python remains development/verification tooling only. The unanswered probe-policy decision is not permission to weaken policy, drop acceptance or introduce another service. No cluster deployment, pod deletion, Trustee modification or backend deletion is authorized by convergence. Reuse validated evidence to close linked tasks rather than repeat destructive tests.

- [X] T084 [R1 HIGH] Complete storage-view pinning in `block-storage-encrypted/scripts/prose-file.sh` and `nfs-direct/scripts/prose-file.sh` and validate the existing plain-chart implementation through independent chart-local `tests/test_startup.py` regressions for mount/path replacement between checking and opening; preserve existing data and prove no temporary-root write, false success or Ready application per FR-023, FR-024, SC-010, US5/AC4–AC5 and T062/T073 (contradicts).
- [ ] T085 [R2 HIGH] Resolve the outstanding T063/T074 policy decision before claiming exec-denying compatibility, then implement the approved Helm/shell probe/verification behavior in the three charts' `templates/deployment.yaml`, `scripts/readiness.sh`, `tests/live.py` and READMEs with supporting fixtures; retain default debug initdata and explicit overrides, add no runtime Python/web service, and keep the requirement blocked if no supported mechanism or explicit scope decision exists per FR-005, FR-018, FR-021 and the restrictive-initdata edge case (partial).
- [X] T086 [R3 HIGH] Finish independent encrypted/NFS integration of the deadline-aware cleanup currently present in `block-storage-plain/tests/live.py` and `tests/live_support.py`; add chart-local full-flow regressions in `tests/test_cleanup_support.py` or equivalent for slow Helm/PV cleanup, eventual backend absence, pending/error adapter results and deadline exhaustion, and update adapter documentation without finalizer or global-policy shortcuts per FR-019, SC-005 and T064/T075 (partial).
- [X] T087 [R4 HIGH] Finish ownership-aware inventory and referenced-resource preservation in `block-storage-encrypted/tests/live.py` and `nfs-direct/tests/live.py`, using independent local support modules; test all three complete cleanup flows with matching-label external objects, controller-owned ReplicaSets/Pods, owned versus referenced envelope Secrets and unchanged external identities/content, preserving NFS data per FR-008, FR-019 and T065/T076 (partial).
- [X] T088 [R5 HIGH] Complete `block-storage-encrypted/tests/test_encrypted_storage.py`, `tests/test_helper_identity.py` and startup/readiness coverage for successful initialization, existing LUKS/XFS reopen without reformat, correct-key mapper reuse, wrong device/mount identity, failures after mapper creation and restart invalidation; assert mutation ordering and current PID/generation publication only after verified mounting per FR-010, FR-018, FR-021 and T066/T077 (partial).
- [X] T089 [R6 HIGH] Replace the unconditional-success storage-check test seam with actual NFS-kind verification coverage in `nfs-direct/tests/test_nfs_mount.py`, `tests/test_storage_access.py` and startup/readiness tests; cover source/type mismatch, delayed/unreachable operations, bounded supervision, read-only/root-squash failure and retained prose, proving no early file write/application readiness without using an inferred live export per FR-014, FR-018, FR-026, SC-010–SC-011 and T067/T078 (partial).
- [X] T090 [R7 HIGH] Complete chart-local collection and disconnected verification in each `tests/live.py`, `tests/verify-live.sh` and associated test modules: require explicit context/namespace/release cohort and mirror expectations, check three examples plus a second release for selection/reference/file isolation, validate admitted images/initdata, and verify remaining releases after explicitly approved removal; add standalone usage guidance without sibling runtime dependencies per FR-008, FR-017, FR-021, SC-002, SC-006–SC-007 and T068/T079 (partial).
- [ ] T091 [R8 HIGH] Complete T028/T040/T048/T056 and T069/T080 only after approved disposable targets, a compatible Delete provider with backend adapter, a test NFS export, the single encryption resource and corrected sealed trust exist; record actual guest source/file verification, two pod replacements, all key modes and negative cases, timeout/propagation behavior, coexistence/disconnected outcomes and backend deletion in `specs/001-add-storage-helm-examples/validation.md`, preserving external resources and keeping unavailable evidence explicitly blocked per SC-001–SC-007, SC-009–SC-012 and FR-027 (partial).
- [X] T092 [R9 MEDIUM] Complete safe override validation in all three `values.schema.json`, `templates/_helpers.tpl`, `tests/test_common_contract.py` and `tests/test_overrides.py` implementations: reject system targets including `/usr`, missing or incoherent CPU/memory budgets for guest RAM/overhead and known floating aliases including `nightly`, while retaining supported maintained mirror/digest overrides per FR-006, FR-015, T005, T070/T081 and plan: strict values/VM resource constraints (partial).
- [X] T093 [R10 MEDIUM] Complete stage-specific errors in all three `scripts/log.sh`, `scripts/main.sh` and `scripts/prose-file.sh`: identify the full demonstration file versus mount path, state when the file check never ran, include the configured deadline and truthful created/unknown outcomes, and test outer/early timeout and file-error paths without sensitive content; reconcile README examples per FR-023, FR-025, SC-010–SC-011, US5/AC3–AC5 and T071/T082 (partial).
- [X] T094 [R11 MEDIUM] Apply supported `resourceAnnotations` to Roles/RoleBindings in each `templates/scc-binding.yaml`, retain protected ownership/identity guards, and test annotation propagation across every owned object kind with scoped SCC binding enabled in each `tests/test_common_contract.py` per FR-006 and T072/T083 (partial).

**Handoff**: Run `/speckit.implement` to complete the shared linked fixes once, marking a task complete only when its full scope is met. Resolve the policy choice explicitly; retain the live evidence gate. Rerun convergence after implementation rather than interpreting additional review tasks as implementation progress.
