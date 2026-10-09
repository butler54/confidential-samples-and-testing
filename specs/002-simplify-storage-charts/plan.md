# Implementation Plan: Readable Storage Helm Examples

**Branch**: `003-simplify-storage-charts` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: `specs/002-simplify-storage-charts/spec.md`

## Summary

Replace the three charts' copied multi-example framework with concrete, independently readable manifests. Use Helm release names directly, fix demonstration-only paths, expose only relevant environment inputs, and retain short shell storage flows with the existing fail-closed safety floor. Prefer explicit repetition over helper indirection. Releases are testing-only: uninstall and reinstall, never upgrade. Completion requires static validation only; no cluster, image, storage or workload execution.

## Technical Context

**Language/Version**: Helm 3.22.0 Go templates, Kubernetes YAML, POSIX shell in existing Red Hat images; Python 3.12.12 only for development-time static parsing/render assertions.

**Primary Dependencies**: Existing Red Hat OSC storage-helper `1.13.1`, UBI `9.6` for encrypted curl retrieval, Helm 3.22.0, existing `shellcheck-py==0.11.0.1` and `PyYAML==6.0.2` development pins. No new runtime dependencies, services, operators or images.

**Storage**: Owned Block/RWO PVC and XFS for both block examples; LUKS2 for encrypted storage; external direct NFS export for NFS. Memory-backed temporary control/key files are never the demonstration-data fallback.

**Testing**: Strict Helm lint, schema-checked positive/negative rendering, YAML/resource assertions, `sh -n`, ShellCheck, package-content/version checks, and human static flow/readability review. No shell-runtime pytest suites, image preflight execution, cluster tests or backend-deletion adapters as acceptance gates.

**Target Platform**: Retain documented bare-metal TDX/SEV-SNP OpenShift/OSC baseline, `kata-cc`, Kubernetes minimum `>=1.33.0-0`, and same-namespace coco-pattern `debug-initdata`. This plan does not independently certify upstream/platform compatibility.

**Project Type**: Three standalone teaching charts, not a shared library or production chart framework.

**Performance Goals**: Reader identifies each flow within 10 minutes. Fixed 2-second polling and configurable bounded startup timeout, default 900 seconds; no throughput/availability SLA.

**Constraints**: No upgrades, runtime Python, package downloads at workload startup, local image builds, extra Trustee resources, policy relaxation or new privilege scope. Corrected sealed trust and guest exec/mount permissions remain documented usage prerequisites, not live completion gates.

**Scale/Scope**: Three single-replica Recreate Deployments; four rendered releases for isolation checks. Root README, chart-local content and existing CI only. Prior feature records and untracked staging samples remain unchanged.

## Constitution Check

*Pre-research gate: PASS. Post-design gate: PASS. No constitutional exceptions requested.*

| Principle | Design evidence |
|---|---|
| I. Self-contained examples | All runtime files, values, documentation and static checks stay within their example; no library/umbrella chart. |
| II. Helm-first | Each retains a standalone Helm chart and values comprehensive for its actual inputs; no Kustomize. |
| III. Downstream-first | Retain existing Red Hat defaults and complete mirrored-reference overrides; development linters are not workload dependencies. |
| IV. External image builds | No image build or new image required. |
| V. CI/version discipline | Static CI on every changed chart; explicit tool/image versions and chart version bump from 0.1.0 to 0.2.0 for breaking test-only values/naming changes. Existing runtime runner will not be used by revised CI. |
| VI. Simplicity | Concrete templates, no custom resource-quantity parsers, no unused roles/options; safety mechanisms retained only for identified failure paths. |

Delivery/workflow checks: keep prerequisites and expected outcomes documented; use applicable static lint/validation and honest evidence. Static review cannot prove guest behavior, CSI reclamation or attestation. The user explicitly excluded those tests from this feature; do not import previous live acceptance gates or mark them complete.

## Project Structure

### Documentation (this feature)

```text
specs/002-simplify-storage-charts/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── contracts/
    ├── values.md
    └── runtime-and-validation.md
```

`tasks.md` is a later `/speckit.tasks` output; do not generate it in planning.

### Source Code (repository root)

```text
block-storage-plain/       # formatter init container + main mounts its own raw device
block-storage-encrypted/   # optional curl init + native storage sidecar + main guest access
nfs-direct/                # main mounts external NFS directly; no init storage container
  Chart.yaml, values.yaml, values.schema.json, .helmignore, README.md
  templates/              # concrete deployment, scripts ConfigMap, account, opt-in SCC
  scripts/                # chart-local shell flow and small justified safety functions
  tests/                  # static renderer/checker, small relevant fixtures, static runner
.github/workflows/validate-examples.yml
README.md
```

Block charts also retain a PVC template. No chart-owned sealed-envelope template is needed: sealed/insecure modes reference operator-owned Secrets. Existing auxiliary tools may be simplified or retired during implementation only after inspecting their purpose; do not change staging or prior specification artifacts.

**Structure Decision**: Specialize existing directories in place. Use `.Release.Name` for base resource names and standard name/instance labels directly; Helm already requires unique release names within a namespace. Every suffix fits the DNS-label limit without truncation/hash name wrappers. Retain a short namespace-derived hash only in demonstration filenames to avoid collisions across namespaces sharing one NFS export. No name overrides or upgrade compatibility.

## Phase 0 — Research Decisions

See [research.md](research.md) for evidence, alternatives and baseline counts. Unknowns are resolved through repository inspection and the two user clarifications, not live probing. Retain proven image/tool identities from previous recorded evidence without rerunning image checks. The real git branch is `003-simplify-storage-charts`; setup reports the feature selector `002-simplify-storage-charts`, which is not the branch name.

## Phase 1 — Design

1. **Concrete manifests**: Delete chart-name branches and unneeded includes. Spell out labels, coco metadata and container roles. Drop arbitrary resource/pod metadata maps, account-create/name variants, checksum rollout logic and unused resource/image settings. Keep only necessary initdata selection, optional image-pull Secrets, scoped SCC opt-in and encrypted mode conditions. Avoid shared helpers; at most two small helpers per chart if genuinely clearer.
2. **Small values surface**: Follow [values contract](contracts/values.md). Fix `/mnt/storage`, mapper/device/control paths and polling interval. Share one `images.storageHelper` reference between application and storage roles because they require the same toolset. NFS has only its application role; encrypted curl adds its own utility role.
3. **Validation in the right place**: Use short chart-specific schemas for types/enums/required values, bounded timeouts and mode-dependent Secret requirements. Do not reimplement Kubernetes CPU/memory quantity parsing, decode/signature-check tokens in Go templates, or copy another chart's properties. Document supported default resource sizing; Kubernetes handles general quantity semantics. Avoid echoing secrets in validation errors.
4. **Readable shell**: Keep an obvious top-to-bottom main entrypoint and formatter/encrypted-helper flow. Remove `SAMPLE_KIND` dispatch and specialize storage checks by chart; keep small chart-local readiness/prose/storage functions where actually reused. Remove the independent timeout-reporting subprocess/`mount.expired` state in favor of bounded preparation plus failure reporting after bounded grace. Retain signature conflict/error handling and whole-device zero verification before formatting, pinned mount access, bounded operations, safe prose handling and encrypted PID/start-generation/backing-device identity with cleanup installed before acquisition. No unsafe stock format fallback, host mount propagation or added runtime service.
5. **Key delivery**: Default curl retrieves the one configured resource via guest CDH. Sealed and insecure modes use one existing Secret reference, differentiated by the explicit mode and guest unsealing contract. No chart-generated envelope Secret or token parser; document authentic vault-token/resource binding and external trust. Never supply plaintext key values through Helm. Reject a still-sealed value rather than pass it to cryptsetup; retain private curl key state for helper restarts, and clear exported PASS before launching child processes.
6. **Lifecycle and permissions**: One Recreate Deployment and owned account per release; memory control volume, no mounted API token. Keep current lab-required privileged in-guest operations and narrowly opt-in SCC Role/RoleBinding. Provider Delete reclamation is external; no destructive hooks or runtime backend checkers.
7. **Static checks and CI**: Replace the broad mixed runner with explicit static-only validation. Reuse useful render assertions but do not invoke legacy runtime tests. Check positive essential overrides and a small invalid-input set, rendered identities/ownership, required images/tool versions, shell syntax/lint and standalone package content. No runtime execution hidden behind the word “offline.”
8. **Teaching documentation**: Short README per example: purpose, prerequisites, values, install example, expected created/existing/failure logs, pod replacement versus destructive uninstall. Do not add upgrade mappings or a live acceptance framework. Record measured simplification and static evidence in this feature's implementation validation report.

### Simplification acceptance

Measurements count all files in `templates/` including NOTES/helpers; values leaves count scalars/lists/empty maps as one. Record before/after counts with the same method; compare schemas and scripts separately so moving complexity does not satisfy the goal.

| Chart | Baseline values leaves | Baseline template lines/actions/helpers | Target values leaves | Target template reduction |
|---|---:|---|---:|---|
| Plain | 34 | 367 / 304 / 11 | ≤20 | ≥25% lines and ≥50% actions; ≤2 helpers |
| Encrypted | 41 | 383 / 313 / 11 | ≤30 | ≥25% lines and ≥50% actions; ≤2 helpers |
| NFS | 37 | 347 / 294 / 11 | ≤17 | ≥25% lines and ≥50% actions; ≤2 helpers |

Zero chart-name storage branching, unused default roles and custom CPU/memory template parsers. These are planning targets supporting a substantive reduction, not permission to minify manifests, remove safety or inflate schema/script complexity. Reviewer walkthrough covers source, preparation, mount gate, keys, prose outcomes and cleanup within 10 minutes per example. Static validation is sufficient for this tranche; runtime claims remain explicitly unverified.

## Complexity Tracking

No constitutional violations. Required encrypted helper/process coordination is storage safety, not a reusable framework. Readability metrics do not justify replacing verified paths with a sleep/marker-only gate.
