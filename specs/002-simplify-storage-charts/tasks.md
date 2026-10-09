---
description: "Executable tasks for simplifying the three confidential-storage teaching charts"
---

# Tasks: Readable Storage Helm Examples

**Input**: Design documents from `specs/002-simplify-storage-charts/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [values contract](contracts/values.md), [runtime/static contract](contracts/runtime-and-validation.md).

**Validation**: Static checks are explicitly required. Only lint, Helm rendering/packaging, YAML/schema/source assertions and human source review are allowed. No workload-shell tests, image execution/pulls, cluster access, mount/format/key operations, pod deletion, release uninstall or backend checks. Install/delete commands in documentation are for future developer use, not execution during this tranche. Chart revisions support delete/recreate only, never upgrades.

**Organization**: Tasks follow the three user stories. Existing working code is the starting point; no new service, generic framework or runtime model layer is needed. All tasks start unchecked; existing research is not implementation evidence.

## Format: `[ID] [P?] [Story] Description`

- `[P]` identifies disjoint chart-local work within the specified batch, after its prerequisites finish. It is not authorization to start dependent tasks early.
- `[US1]`, `[US2]`, `[US3]` map directly to the specification's stories.
- Paths are repository-relative. Every example must remain independent; no sibling runtime/static-check imports.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish a bounded change inventory and reproducible static tooling without executing the workloads.

- [X] T001 Create `specs/002-simplify-storage-charts/validation.md` with the baseline values-leaf/template-line/action/helper counts from `research.md`, source/schema/script complexity notes, and the static-only/delete-recreate scope; record the initial worktree state and explicitly exclude `staging/` and `specs/001-add-storage-helm-examples/` from changes.
- [X] T002 Configure development-only static dependencies in `block-storage-plain/tests/requirements.txt`, `block-storage-encrypted/tests/requirements.txt`, and `nfs-direct/tests/requirements.txt`: retain `PyYAML==6.0.2` and `shellcheck-py==0.11.0.1`, remove pytest if no static checker uses it, and record available Helm/Python/linter versions in `specs/002-simplify-storage-charts/validation.md` without pulling or executing workload images.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make static validation safe before replacing the copied chart framework.

- [X] T003 Inspect existing `block-storage-plain/tests/`, `block-storage-encrypted/tests/`, and `nfs-direct/tests/`; classify useful render/package/source assertions versus runtime-shell/CLI/image/live tooling in `specs/002-simplify-storage-charts/validation.md`, recording specific candidates for reuse/retirement without executing them or deleting uninvestigated files.
- [X] T004 Replace `block-storage-plain/tests/run.sh`, `block-storage-encrypted/tests/run.sh`, and `nfs-direct/tests/run.sh` with short static-only entrypoints for strict Helm lint, chart-local `tests/static.py`, `sh -n`, ShellCheck and package/metadata checks; provide documentation-only NFS fixture inputs, restrict validation tools to static commands, and do not invoke the runners until the corresponding checker exists.

**Checkpoint**: Safe static entrypoints and tool inventory are ready. Do not run legacy pytest or image/live scripts to obtain a baseline.

## Phase 3: User Story 1 — Understand One Example Directly (Priority: P1) — MVP

**Goal**: A reader can follow each example's concrete default flow without chart-kind dispatch, generic naming/quantity parsers, unused roles or sibling dependencies.

**Independent Test**: Render/lint one example alone and trace its source, preparation, application-visible storage, file outcomes and cleanup from its own files/README. Inspect its source for zero chart-name storage branching and unused configuration. No runtime execution is needed.

### Static checks for User Story 1

Write the following checks first and confirm that the legacy source/render fails the new simplification assertions through static execution only. Keep the checker small; do not translate the entire old suite into another framework.

- [X] T005 [P] [US1] Create `block-storage-plain/tests/static.py` with default render assertions for release-based names/selectors, one formatter init plus application, Block/RWO claim/default class omission, no unrelated NFS/encryption/utility settings, and source assertions rejecting generic chart-kind/quantity helpers; retain useful audited static assertions from T003.
- [X] T006 [P] [US1] Create `block-storage-encrypted/tests/static.py` with default curl topology, native helper sidecar/shared PID, release-based names/selectors, owned claim, external references and source assertions rejecting copied NFS/plain variants and template token/quantity parsers.
- [X] T007 [P] [US1] Create `nfs-direct/tests/static.py` with documentation-only NFS inputs and assertions for one direct-mount application, no PV/PVC/helper/utility/key settings, release-based identity and no generic storage-kind helpers.

### Implementation for User Story 1

- [X] T008 [P] [US1] Specialize `block-storage-plain/values.yaml`, `block-storage-plain/values.schema.json`, and `block-storage-plain/templates/` to the values contract: direct release names/labels, owned account/claim, formatter/application using one storage-helper image, literal demonstration paths, relevant resources and small genuine conditionals; remove unused options, quantity/token parsers and obsolete helper indirection while preserving valid default renders.
- [X] T009 [P] [US1] Specialize `block-storage-encrypted/values.yaml`, `block-storage-encrypted/values.schema.json`, and `block-storage-encrypted/templates/` to the values contract, including the common existing Secret reference for sealed/insecure modes, curl default/native sidecar, one configured resource and release identity; remove the investigated chart-owned `block-storage-encrypted/templates/sealed-secret.yaml`, inline-envelope option, unrelated branches and custom parsers.
- [X] T010 [P] [US1] Specialize `nfs-direct/values.yaml`, `nfs-direct/values.schema.json`, and `nfs-direct/templates/` to direct NFS only: one application, required server/export/options, no block storage/helper roles or unused settings, direct release identity and relevant coco/account/SCC metadata.
- [X] T011 [P] [US1] Specialize `block-storage-plain/scripts/main.sh`, `block-storage-plain/scripts/storage-access.sh`, and their local call sites to the plain flow; remove `SAMPLE_KIND` and irrelevant encrypted/NFS paths, adapt fixed paths/inputs to T008, and preserve the existing safety behavior pending the focused US2 review.
- [X] T012 [P] [US1] Specialize `block-storage-encrypted/scripts/main.sh`, `block-storage-encrypted/scripts/storage-access.sh`, and their local call sites to encrypted helper access; remove plain/NFS dispatch, adapt key/reference/mapper inputs to T009, and preserve generation-aware access and existing safety behavior.
- [X] T013 [P] [US1] Specialize `nfs-direct/scripts/main.sh`, `nfs-direct/scripts/storage-access.sh`, and their local call sites to direct NFS; remove plain/encrypted dispatch and irrelevant files only after investigating them, adapting fixed inputs to T010 without removing bounded mount/file safeguards.
- [X] T014 [US1] Rewrite `block-storage-plain/README.md`, `block-storage-encrypted/README.md`, and `nfs-direct/README.md` as concise standalone default-flow guides; explain source/preparation/mount/prose/cleanup, testing-only delete/recreate and prerequisites, then run the revised static entrypoints and record default render/readability findings in `specs/002-simplify-storage-charts/validation.md`.

**Checkpoint**: Concrete defaults are independently understandable and statically valid. US1 is the MVP; unchanged core safety must not be weakened to reach it.

## Phase 4: User Story 2 — Run the Same Storage Demonstrations (Priority: P1)

**Goal**: Preserve the original storage/prose/lifecycle intent with short, specialized shell and no false-success or destructive fallback paths. “Run” is intended developer behavior, not authorization to execute workloads for acceptance.

**Independent Test**: Lint shell and statically trace preparation → intended mounted source → pinned main-visible access → safe prose → current readiness. Inspect all five specified failure classes and owned/external cleanup boundaries. Report source evidence, not persistence/encryption/reclamation test results.

### Static checks for User Story 2

- [X] T015 [P] [US2] Extend `block-storage-plain/tests/static.py` with source/render guards for fail-closed signature/size/whole-device-zero inspection, compatible XFS reuse, main-container block source, pinned file view, safe creation/existing verification, current storage readiness, owned persistent claim and no keep/deletion hook; validate structure/text only, never invoke shell entrypoints.
- [X] T016 [P] [US2] Extend `block-storage-encrypted/tests/static.py` with source/render guards for selected key transport without fallback/disclosure, existing LUKS/key/backing-device checks, cleanup-before-acquisition, helper PID/start-generation identity, proc-root access, pinned file operations and current readiness; never execute cryptsetup/helper/key scripts.
- [X] T017 [P] [US2] Extend `nfs-direct/tests/static.py` with source/render guards for direct expected-source NFS mounting, bounded operations/termination cleanup, pinned prose access, read-only/mismatch failure paths and readiness tied to current storage; never execute mount, timeout scenarios or file-operation scripts.

### Implementation for User Story 2

- [X] T018 [US2] Simplify `block-storage-plain/scripts/device.sh`, `block-storage-plain/scripts/format-storage.sh`, `block-storage-plain/scripts/mount-storage.sh`, `block-storage-plain/scripts/main.sh`, `block-storage-plain/scripts/storage-access.sh`, `block-storage-plain/scripts/prose-file.sh`, `block-storage-plain/scripts/readiness.sh`, and `block-storage-plain/scripts/log.sh`: retain blank-media proof/XFS reuse, pinned safe prose and explicit status; replace duplicate startup reporting/deadlines with one bounded preparation budget plus finite grace, no general supervisor or temporary-storage success path.
- [X] T019 [US2] Simplify `block-storage-encrypted/scripts/fetch-key.sh`, `block-storage-encrypted/scripts/key.sh`, `block-storage-encrypted/scripts/device.sh`, and `block-storage-encrypted/scripts/encrypted-storage.sh`: retain bounded private guest-CDH curl retrieval, genuine guest-unsealed PASS versus explicitly insecure PASS, still-sealed rejection, key verification with existing mapper, backing checks and cleanup-before-acquisition; keep private curl state for helper restarts and clear exported PASS before children without logging key bytes.
- [X] T020 [US2] Simplify `block-storage-encrypted/scripts/main.sh`, `block-storage-encrypted/scripts/storage-access.sh`, `block-storage-encrypted/scripts/prose-file.sh`, `block-storage-encrypted/scripts/readiness.sh`, and `block-storage-encrypted/scripts/log.sh`: preserve PID/start-generation/mount-source checks and pinned proc-root filesystem access, safe prose/current readiness and explicit outcomes; remove redundant timeout reporter/dispatcher state without guessing PID or trusting only a marker.
- [X] T021 [US2] Simplify `nfs-direct/scripts/mount-storage.sh`, `nfs-direct/scripts/main.sh`, `nfs-direct/scripts/storage-access.sh`, `nfs-direct/scripts/prose-file.sh`, `nfs-direct/scripts/readiness.sh`, and `nfs-direct/scripts/log.sh`: retain quoted direct NFS source/options, bounded hard-mount/file operations, pinned safe prose, current readiness and bounded NFS-only termination unmount; remove redundant reporter/dispatcher state without extending privilege scope.
- [X] T022 [US2] Run the revised static entrypoints and review ownership/pod-replacement references in `block-storage-plain/templates/pvc.yaml`, `block-storage-encrypted/templates/pvc.yaml`, and each chart's `templates/deployment.yaml`/`templates/scc-binding.yaml`; record the five failure-class source reviews, owned-versus-external cleanup and unverified runtime limits in `specs/002-simplify-storage-charts/validation.md` without accessing a provider or cluster.

**Checkpoint**: Core behavior and safety intent have explicit static evidence; no actual mount, persistence, attestation, encryption or provider deletion is claimed.

## Phase 5: User Story 3 — Configure Only What the Example Needs (Priority: P2)

**Goal**: Essential environment/Trustee/mirror inputs remain usable and isolated, without restoring generic framework options.

**Independent Test**: Render documented overrides and invalid inputs independently for each chart; compare four release renders and filename identity across namespaces. Every input maps to a retained requirement; no deployment or real key/token is needed.

### Static checks for User Story 3

- [X] T023 [P] [US3] Extend `block-storage-plain/tests/static.py` for default/explicit class and capacity, storage-helper mirror applied to both roles, pull references/resources, initdata precedence/cluster-default selection, scoped SCC opt-in, unknown/invalid-key rejection, maximum-length release names and stable isolated claim/prose references.
- [X] T024 [P] [US3] Extend `block-storage-encrypted/tests/static.py` for all three key-mode renders, missing/conflicting Secret and invalid resource/mode rejection, helper/utility mirror coverage, pull/resource/initdata/SCC overrides, no emitted external Secrets, maximum release names and isolation; fixtures must contain references only, no secret/token values.
- [X] T025 [P] [US3] Extend `nfs-direct/tests/static.py` for required/invalid server/export/options including IPv6 source rendering, only consumed-image/resource overrides, initdata/pull/SCC cases, absent block/key options, long release names and namespace-isolated prose filenames.

### Implementation for User Story 3

- [X] T026 [US3] Complete and correct essential initdata and privilege metadata handling in `block-storage-plain/templates/deployment.yaml`, `block-storage-encrypted/templates/deployment.yaml`, and `nfs-direct/templates/deployment.yaml`: inline encoded data wins, absent encoded data uses configured `debug-initdata`, empty ConfigMap name selects cluster default, appropriate skip-injection labels are present, and opt-in SCC references remain account-scoped with no policy relaxation or generic metadata map.
- [X] T027 [US3] Complete and correct the chart-specific input validation/override wiring in `block-storage-plain/values.schema.json`, `block-storage-encrypted/values.schema.json`, `nfs-direct/values.schema.json` and their `templates/deployment.yaml` files; use the US3 checks to close class/capacity/image/resource/Secret/NFS gaps, reject unknown/invalid inputs, and keep mode-dependent conditions short rather than reintroducing token/quantity/framework parsers.
- [X] T028 [P] [US3] Add a compact essential-values/override section and updated `block-storage-plain/templates/NOTES.txt` to `block-storage-plain/README.md`, covering class/capacity/mirrors/initdata/pull/SCC inputs, expected logs and destructive release cleanup versus safe pod replacement; no legacy-setting mapping or live-validation runner dependency.
- [X] T029 [P] [US3] Add a compact essential-values/key-mode section and updated `block-storage-encrypted/templates/NOTES.txt` to `block-storage-encrypted/README.md`, covering curl default, existing signed-token/explicitly insecure Secret references, the one resource, corrected guest trust, mirrors/initdata/exec permission prerequisites and destructive cleanup; no plaintext example key or signature bypass.
- [X] T030 [P] [US3] Add a compact essential-values/override section and updated `nfs-direct/templates/NOTES.txt` to `nfs-direct/README.md`, covering server/export/options, mirrors/initdata/pull/SCC inputs, required writable guest access and preservation of external export/data on uninstall; no provisioning or live-tool dependency.
- [X] T031 [US3] Statically compare `plain`, `encrypted`, `nfs`, and `plain-two` renders in one namespace plus a second-namespace filename case using the chart-local checkers in `block-storage-plain/tests/static.py`, `block-storage-encrypted/tests/static.py`, and `nfs-direct/tests/static.py`; correct any naming/selector/data collision and record isolation/ownership evidence in `specs/002-simplify-storage-charts/validation.md` without introducing sibling checker dependencies.

**Checkpoint**: All essential inputs and key alternatives render with expected identities/ownership; no unused cross-chart options remain.

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish packaging, static CI and honest simplification evidence; no new feature or live acceptance phase.

- [X] T032 Bump `block-storage-plain/Chart.yaml`, `block-storage-encrypted/Chart.yaml`, and `nfs-direct/Chart.yaml` to chart version `0.2.0`, retain the explicit app/image/platform baseline, and update each `.helmignore` plus static package/version assertions so packages are standalone and contain no tests, development Python or obsolete runtime files.
- [X] T033 Reuse or retire only specifically investigated obsolete framework tests/fixtures/tooling in `block-storage-plain/tests/`, `block-storage-encrypted/tests/`, and `nfs-direct/tests/` according to T003; remove stale references to removed inputs, prevent legacy runtime/live scripts from being invoked by guides/CI, and record exact dispositions in `specs/002-simplify-storage-charts/validation.md` without broad deletion or changes to user staging/prior specs.
- [X] T034 Update `.github/workflows/validate-examples.yml` to call only revised static entrypoints in its independent chart matrix, retaining pinned checkout/Helm/Python dependencies and read-only permissions; do not supply kubeconfig/registry secrets, invoke pytest/runtime scripts or add live/image/backend jobs.
- [X] T035 Update `README.md` and `specs/002-simplify-storage-charts/quickstart.md` to the final concise example index and actual static commands, remove the transitional legacy-runner warning only after T004 is implemented, and state delete/recreate plus static evidence limits without upgrade/live requirements.
- [X] T036 Measure before/after values leaves, template lines/actions/helpers and schema/script indirection for every chart in `specs/002-simplify-storage-charts/validation.md`; check the plan targets (≤20/30/17 leaves, ≥25% template-line and ≥50% action reductions, ≤2 helpers), zero chart-kind dispatch/quantity parsers/unused roles, and record a ≤10-minute per-example source walkthrough without minification, relocated complexity or fabricated human/runtime results.
- [X] T037 Execute only the final static scenarios from `specs/002-simplify-storage-charts/quickstart.md`, review the finished diff against `specs/002-simplify-storage-charts/spec.md` and `.specify/memory/constitution.md`, and finalize `specs/002-simplify-storage-charts/validation.md` with real tool/results/limitations; distinguish local checks from observed GitHub CI, which must pass before merge but is not authorization to commit/push/open a PR.

## Dependencies & Execution Order

### Phase dependencies

```text
Setup T001–T002
    → Foundation T003–T004
    → US1 T005–T014 (concrete readable defaults / MVP)
    → US2 T015–T022 (focused static safety/lifecycle review)
    → US3 T023–T031 (essential overrides / isolation)
    → Polish T032–T037
```

The stories are independently **verifiable**, but their refactors touch the same files: do not claim they are independent implementation streams. US2/US3 build on US1's revised interface; US3 validation follows the core safety pass. Cross-chart batches have disjoint files; tasks writing the shared validation report remain serial.

### Within-story dependencies

- US1: T005–T007 static checks first → T008–T010 concrete templates/values → T011–T013 corresponding shell call sites → T014 documentation/default checks. Each shell task requires its corresponding template task; wait for the batch before the shared checkpoint.
- US2: T015–T017 static guards first → T018 plain, T019→T020 encrypted, T021 NFS → T022 combined static review. Different chart implementations may be scheduled separately, but never concurrently with another task editing their scripts/checker.
- US3: T023–T025 checks first → T026 common metadata wiring → T027 remaining input gaps → T028–T030 independent docs → T031 isolation review.
- Polish: packaging/retirement precede final CI/guide validation; T036–T037 use final content. Do not mark T037 complete from historical results.

### Parallel opportunities

- US1 checker batch T005/T006/T007; template batch T008/T009/T010 after the checker batch; shell batch T011/T012/T013 after corresponding templates.
- US2 checker batch T015/T016/T017. Plain, encrypted and NFS safety implementation can be divided by directory; T020 follows T019.
- US3 checker batch T023/T024/T025; documentation batch T028/T029/T030 after input wiring.
- `[P]` is a scheduling opportunity, not a requirement to delegate or use multiple agents.

## Parallel Example: User Story 1

```text
After T004:
T005: plain tests/static.py
T006: encrypted tests/static.py
T007: NFS tests/static.py

After those checks are written/run statically:
T008: plain values/schema/templates
T009: encrypted values/schema/templates
T010: NFS values/schema/templates
```

## Parallel Example: User Story 2

```text
After US1:
T015: plain static safety assertions
T016: encrypted static safety assertions
T017: NFS static safety assertions

Then separate chart-directory lanes:
T018 plain | T019 → T020 encrypted | T021 NFS
Join at T022; no workload scripts are executed.
```

## Parallel Example: User Story 3

```text
After US2:
T023 plain overrides | T024 encrypted overrides | T025 NFS overrides
Then T026 → T027.
T028 plain guide | T029 encrypted guide | T030 NFS guide
Join at T031 static isolation comparison.
```

## Implementation Strategy

### MVP First (User Story 1)

Finish Setup/Foundation, then concrete templates and specialized default startup per chart. Stop at T014 for static checks and a default-flow source walkthrough. Plain may be the first working slice, but the US1 MVP covers all three readable defaults. Retain existing safety while refactoring; do not ship a stripped unsafe sketch.

### Incremental Delivery

1. US1 removes irrelevant abstraction and exposes an understandable default path.
2. US2 simplifies necessary safety/lifecycle code with explicit static evidence.
3. US3 verifies essential portability/key alternatives and resource/data isolation.
4. Polish records real reductions, standalone packaging and static-only CI. No runtime/live stage, upgrade adapter or accumulated convergence phase is added.

### Notes

- Do not execute workload scripts even with mocked tools: that is runtime validation, not static validation.
- No secret/token bytes in fixtures, logs or validation artifacts; use synthetic nonsecret metadata/Secret references only.
- All retained functions, values and components must map to a real requirement. Count reductions are not permission to remove storage safety.
- Require actual revised GitHub CI success before merge; do not fabricate it or infer permission for Git operations from task generation.
- Preserve untracked `staging/` files and prior feature records. No task is completed merely by generating this list.
