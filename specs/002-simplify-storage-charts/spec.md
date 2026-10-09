# Feature Specification: Readable Storage Helm Examples

**Feature Branch**: `003-simplify-storage-charts`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "The previous spec generated comprehensive, however, complex examples. These are meant to be examples which are readable for human developers. While providing the core capability simplify the charts as much as possible. Reduce unnecessary templating."

## Clarifications

### Session 2026-10-09

- Q: Must the simplified charts support upgrading existing releases without reinstalling them? → A: No. These are testing-only examples; chart changes use delete and recreate, not upgrades.
- Q: Should completing this simplification require live cluster testing, or can local tests and CI establish completion while live testing remains separately tracked? → A: No live cluster testing. Completion uses only linting and validation that can be performed statically.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand One Example Directly (Priority: P1)

A developer opens an example to learn how confidential storage works. They can follow its own storage attachment, preparation, mount, and main-container startup without decoding a generic framework or branches for the other examples.

**Why this priority**: Teaching developers is the primary purpose; configuration flexibility must not obscure the demonstration.

**Independent Test**: Review any one example alone and explain its storage source, preparation steps, readiness gate, file behavior, and cleanup using only that directory's deployment content and README.

**Acceptance Scenarios**:

1. **Given** the plain-block example, **When** a developer reads its default deployment, **Then** only the plain-block flow is presented; encryption and NFS variants are not part of the explanation they must unravel.
2. **Given** the encrypted example, **When** a developer follows its startup, **Then** the chosen key-delivery path and encryption/mount sequence are clear, with only the necessary alternatives selectable.
3. **Given** the direct-NFS example, **When** a developer reads its configuration and workload, **Then** the server/export and direct mount are clear, with no unrelated block-claim, encryption, or unused-container configuration.

---

### User Story 2 - Run the Same Storage Demonstrations (Priority: P1)

A platform engineer uses the simpler examples on a prepared Red Hat confidential-container cluster. Simplification preserves useful demonstration behavior rather than turning working examples into incomplete pseudocode.

**Why this priority**: Readability must not remove the storage capability or essential data/key safety.

**Independent Test**: Statically inspect each example's rendered deployment and startup logic for storage preparation, mount gating, prose creation/verification, persistent storage across pod replacement, selected key delivery, and ownership-aware cleanup. Lint and validate without deploying workloads or executing storage operations; the following scenarios define intended behavior, not live acceptance gates.

**Acceptance Scenarios**:

1. **Given** compatible default block provisioning, **When** either block example starts, **Then** it prepares only appropriate blank media, makes the intended filesystem available to the main container, and preserves compatible existing data; the encrypted example encrypts and unlocks inside the guest.
2. **Given** a writable existing NFS export, **When** the NFS example starts, **Then** it mounts the export directly inside the workload without a persistent-volume interface and runs the same file demonstration.
3. **Given** accessible intended storage, **When** the main entrypoint starts, **Then** it creates and verifies the public prose file if absent, or logs that the existing file contains the expected prose without rewriting it; other outcomes produce explicit failure without overwriting data or using temporary storage as a fallback.
4. **Given** a running example with stored prose, **When** its pod is deleted, **Then** its Deployment creates a replacement that accesses the same data and reports the existing-file outcome.
5. **Given** an approved disposable release, **When** it is uninstalled, **Then** release-owned artifacts and block claims/backing volumes are removed through compatible provider reclamation, while external NFS data and pre-existing infrastructure remain untouched.

---

### User Story 3 - Configure Only What the Example Needs (Priority: P2)

A developer adapts an example to their namespace, storage, Trustee setup, or disconnected image mirror using a small, relevant set of clearly documented values.

**Why this priority**: Essential portability remains useful; speculative framework options and unused settings distract from learning.

**Independent Test**: Render each example with its documented essential overrides without editing packaged deployment content or consulting a sibling. Compare rendered resources and configured data identities for the three examples and another independently named release to check isolation without deploying them.

**Acceptance Scenarios**:

1. **Given** a coco-pattern workload namespace, **When** an example is installed without an initdata override, **Then** it selects `debug-initdata`; a documented explicit override remains available and takes precedence when supplied.
2. **Given** an operator-specified compatible storage class or mirrored images, **When** the corresponding essential values are overridden, **Then** the example uses those inputs without public-registry/package access during workload startup.
3. **Given** one Trustee encryption-key resource and the documented trust prerequisites, **When** the engineer selects curl, CoCo sealed-token, or explicitly insecure existing-Secret delivery, **Then** the encrypted demonstration uses that single selection without an insecure fallback or another Trustee demonstration resource.
4. **Given** independently named releases in one namespace, **When** all examples run together and one release is removed, **Then** resources/selectors/data identities remain isolated and the other releases continue working.

### Edge Cases

- A mount is delayed, disappears, or resolves to the wrong storage: no demonstration-file write or success on temporary storage; the application does not become falsely ready.
- A key is missing/denied/wrong, or media has incompatible signatures/probe errors: fail without exposing key material, downgrading delivery, or destructive conversion.
- A prose file exists with unexpected content, cannot be read, or cannot be created on a read-only export: report the actual outcome and preserve existing content.
- A shortened release identity or a shared NFS export is used: preserve isolation without silently colliding with another release's resource or file.
- An existing test release needs the simplified chart: uninstall and reinstall explicitly; in-place upgrades are unsupported. Explain that deleting a block release removes its owned storage, unlike replacing only its pod.
- Corrected sealed-token trust, raw-block/Delete provisioning, guest NFS support, or required probe/mount permissions are absent: identify the external prerequisite, not a reason to introduce new services or automatic infrastructure changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Simplify the existing `block-storage-plain`, `block-storage-encrypted`, and `nfs-direct` examples in place. Each MUST remain a self-contained root-level Helm chart, not a generic framework, umbrella chart, or runtime-dependent sibling.
- **FR-002**: Each chart MUST directly present its own concrete storage flow. A reader MUST NOT need to interpret chart-name-driven variants or unrelated storage scenarios to understand the selected example.
- **FR-003**: Templating MUST be limited to essential environment inputs, release isolation, and genuine selectable behavior. Every retained helper, conditional, and exposed setting MUST have a clear purpose tied to a retained requirement; unused/cross-example settings and redundant indirection MUST be removed. Small explicit repetition is acceptable when clearer than abstraction.
- **FR-004**: The main learning path MUST explain storage preparation, application-visible mount gating, and prose-file handling clearly within the example. Deployment MUST NOT depend on understanding auxiliary validation frameworks or installing an additional runtime application/service. Runtime Python, new web services, and local image builds are outside this feature.
- **FR-005**: Preserve the three core flows: safe unencrypted raw-block formatting/mounting, in-guest block encryption/unlocking/mounting, and direct mounting of an existing NFS export without a Kubernetes persistent-volume interface.
- **FR-006**: Preserve the Deployment lifecycle and prose demonstration: mount access before file operations, verified creation only when absent, verification without recreation when present, explicit failure otherwise, and original data accessible across pod replacement. These are testing-only examples: chart changes MUST use explicit release deletion and recreation, not in-place upgrades. Backward-compatible resource names, selectors, and configuration are not required across chart revisions.
- **FR-007**: Preserve essential key/media safety without building a general validation framework: no destructive conversion of existing/incompatible media, no treating inspection errors as blank media, no unencrypted or insecure key-delivery fallback, no key/arbitrary-content logging, and no false readiness or temporary-root file writes.
- **FR-008**: Preserve coco-pattern metadata interoperability, default same-namespace `debug-initdata`, and documented initdata overrides with explicit-data precedence. Supported overrides MUST allow operations/probes required by the example; charts MUST NOT silently relax the chosen policy.
- **FR-009**: Block examples MUST use the default storage class when unspecified and allow explicit compatible class/capacity selection. NFS MUST expose only relevant server/export/mount inputs, not unused block provisioning settings. All consumed containers MUST retain maintained Red Hat-preferred defaults and full image overrides for disconnected use, with no workload-startup package downloads.
- **FR-010**: The encrypted example MUST retain exactly one selected key-delivery mode: attested curl through the supported guest access path, genuine CoCo sealed-token delivery, or explicitly insecure existing Kubernetes Secret delivery. Both attested modes MUST reference the one preconfigured encryption resource; corrected upstream sealed trust remains an external prerequisite, not an implicit signature bypass.
- **FR-011**: Preserve unique chart/release resource names, selectors, and demonstration-file identities so all examples and another release coexist. Shared pre-existing resources MUST remain referenced, not adopted. Namespace-wide/cluster-wide privilege grants or infrastructure provisioning MUST NOT be added to reduce setup steps.
- **FR-012**: Preserve uninstall semantics: owned artifacts and block claims are removed, compatible Delete reclamation removes backing volumes, and external NFS data/infrastructure remains untouched. Documentation MUST distinguish pod replacement from destructive uninstall and explain provider/trust/permission prerequisites plainly.
- **FR-013**: Keep a short root README index and concise standalone example guides covering purpose, prerequisites, normal deployment, essential overrides, expected logs, verification and cleanup. State that only delete-and-recreate installation is supported across chart revisions, warn about owned block-data deletion, and do not provide upgrade compatibility or legacy-setting mappings.
- **FR-014**: Feature completion MUST require only static linting and validation: chart rendering, manifest/configuration and version checks, shell linting, and review of core behavior/safety logic. No live cluster testing, workload/runtime execution, image execution, or provider-deletion evidence is required or authorized by this feature. Simplification MUST show a net reduction in default configuration and templating indirection for every chart, not merely relocate the same framework elsewhere. Report the limits of static evidence without claiming runtime behavior was verified; live acceptance tasks and exhaustive speculative policy/configuration matrices are outside this feature.

### Key Entities

- **Example**: One independently readable/deployable storage demonstration and its essential inputs.
- **Release**: One isolated test installation with stable storage/resource identity across pod replacement, but no upgrade compatibility across chart revisions.
- **Demonstration File**: Public expected prose whose creation or verified prior existence makes storage persistence observable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the three examples, a developer familiar with deployments can identify its storage source, preparation sequence, key source if applicable, file outcomes, and cleanup consequences within 10 minutes using only that example's content and guide.
- **SC-002**: Every exposed input and default setup step maps to a retained requirement; zero inputs or steps are present solely for another demonstration. A before/after review records a net reduction in configuration choices and explanatory indirection for all three examples.
- **SC-003**: All three examples pass static validation; review identifies explicit creation/readback and existing-file paths, persistent storage references across pod replacement, and all three supported encrypted key-delivery paths. No live execution is needed to complete this feature, and these findings are not claimed as proof of runtime persistence or encryption.
- **SC-004**: Static comparison of four independently named instances finds zero unintended resource/data-identity collisions or cross-release ownership references. Cleanup configuration and documentation distinguish owned block reclamation from preserved external resources/data; actual reclamation is not claimed as tested.
- **SC-005**: Static review covers all five failure classes—missing/wrong keys, unavailable/wrong storage, incompatible media, prose mismatch, and inspection errors—with no identified destructive conversion, insecure fallback, false-success path, secret disclosure, or fallback write. Essential initdata and mirror overrides render without editing packaged deployment content; all applicable static lint/validation checks pass.

## Assumptions

- This is a simplification tranche, not another platform feature. It preserves the core capabilities listed here from `specs/001-add-storage-helm-examples/spec.md`; it does not automatically carry forward every incidental framework option or accumulated convergence task from that feature.
- Developers can read ordinary workload manifests and short shell startup logic. Optimize for understanding one example, not maximizing reuse between example implementations.
- The existing supported Red Hat/coco-pattern lab environment and debug-initdata path remain the baseline. Arbitrary all-exec-denying-policy compatibility, additional health services, key rotation, server/operator provisioning and production-policy hardening are not new goals.
- Configuration remains comprehensive for the actual example as required by the constitution, but not for unused container roles, unrelated variants or speculative customization. Existing generic options and naming conventions may be removed without upgrade compatibility; release deletion/recreation is explicit and destructive block cleanup must be documented.
- A prepared cluster, CSI/Delete provider, external NFS export, one encryption resource, and corrected sealed trust remain prerequisites for a developer's eventual use, not completion dependencies for this tranche. Validation is static only; this feature neither fixes upstream trust nor runs, requires, or claims live acceptance.
- Existing untracked staging samples and prior feature artifacts remain untouched. Baseline size/readability measurements and implementation choices belong in planning; code is not changed by this specification command.
