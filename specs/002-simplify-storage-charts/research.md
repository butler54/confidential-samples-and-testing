# Phase 0 Research: Simplifying the Teaching Charts

**Date**: 2026-10-09. **Status**: Complete. Repository inspection and one read-only research agent only; no tests, workload scripts, images, cluster access or external requests. Prior compatibility findings are carried forward, not independently revalidated.

## R1 — Scope and compatibility

**Decision**: Testing-only delete/recreate releases. No chart-upgrade compatibility, legacy names, values mappings or data migration. Complete through static lint/validation only.

**Rationale**: The two [user clarifications](spec.md#clarifications) expressly remove upgrades and live acceptance. Existing Deployment/PVC identity must persist across pod replacement, not across chart revisions.

**Alternatives considered**: Preserve old hashed naming and mapping helpers; require live persistence/key-mode/provider tests. Both conflict with the clarified scope. Intended storage behavior remains required, but static results cannot prove runtime behavior.

## R2 — Concrete templates and relevant configuration

**Decision**: Specialize each deployment, schema and script to its storage kind. Use full `.Release.Name` with short suffixes, literal standard labels, fixed demonstration paths/poll interval and one storage-helper image value for tool-complete roles. Remove arbitrary metadata maps, existing-account variants, unused image/resource roles and quantity-parsing helpers. Keep a small opt-in account-scoped SCC binding and genuine encrypted mode alternatives.

**Rationale/evidence**: `block-storage-plain/templates/deployment.yaml` and its peers contain encrypted/NFS branches. Each `_helpers.tpl` defines 11 helpers, including base64 decoding, CPU/memory arithmetic and properties for other charts. `nfs-direct/values.yaml` exposes block size/class and helper/utility resources despite rendering one application. Helm namespace release uniqueness already solves resource isolation; its 53-character release limit plus `-scripts` remains under 63.

**Alternatives considered**: A library chart; relocating generic validation into a large schema; keeping helpers merely because files are identical. These obscure standalone teaching flows. Namespace-hashed, readable chart/release prose names are retained because two namespaces can reference the same NFS export.

### Measured baseline

Counts are source-only, before implementation: all template files including NOTES/helpers; `{{` occurrences count actions; default scalar/list/empty-map nodes count values leaves.

| Chart | Values leaves | Template files | Lines | Actions | Helper definitions | Includes |
|---|---:|---:|---:|---:|---:|---:|
| Plain | 34 | 7 | 367 | 304 | 11 | 37 |
| Encrypted | 41 | 8 | 383 | 313 | 11 | 39 |
| NFS | 37 | 6 | 347 | 294 | 11 | 35 |

Each schema is 30 physical lines but densely contains other charts' properties; physical line count alone is not readability evidence. Compare schema properties/branches and runtime script dispatch separately. The plan's targets require reduction, not minification.

## R3 — Storage safety that must survive simplification

**Decision**: Retain fail-closed inspection, no-signatures plus whole-device zero proof before format, compatible-media reuse, helper key/backing verification, current PID/start-generation state, pinned application-visible storage and safe prose handling. Specialize repeated branches and simplify logging/deadline orchestration instead of removing safety.

**Rationale/evidence**:

- `block-storage-plain/scripts/device.sh` requires successful signature/size inspection and bounded whole-device comparison; no signature is not proof of blank media.
- `block-storage-encrypted/scripts/encrypted-storage.sh` owns mapper/mount cleanup and existing-volume/key checks; native sidecar restarts need generation-aware state.
- `block-storage-encrypted/scripts/storage-access.sh` validates helper PID generation and mount source. Shared PID namespaces do not share mounts; `/proc/<pid>/root` access remains part of this minimal supported design.
- `scripts/prose-file.sh` pins the storage view, refuses unsafe existing files, creates without clobbering and verifies exact content; `scripts/readiness.sh` checks both prose completion and current storage.
- The three `scripts/main.sh`/`storage-access.sh` files carry the same cross-kind dispatcher. Remove that dispatcher, redundant logs/checks and separate timeout reporter state; keep one bounded startup preparation with finite cleanup grace and per-operation bounds.

**Alternatives considered**: Stock `luks-helper format-disk`, fixed sleeps/PID, marker-only readiness, generic mount supervisors or a health web service. They either regress safety or add unnecessary architecture. Small local shared shell functions are reasonable; a sibling runtime dependency is not.

## R4 — Preserve real key modes without token templating

**Decision**: Curl remains default, via guest-local CDH and the one configured resource; sealed/insecure paths use a common existing Secret name/key reference. Drop chart-owned inline envelopes and Go-template token decoding. Sealed tokens must genuinely identify the configured vault resource and rely on corrected external signing trust/agent unsealing.

**Rationale/evidence**: `block-storage-encrypted/scripts/fetch-key.sh` uses guest CDH, finite requests and private validated key transport. `encrypted-storage.sh` rejects still-sealed PASS, clears exported key state, and keeps curl bytes privately available for native sidecar restart. Existing-Secret sealed mode already prevents Helm from inspecting token content; cryptographic acceptance belongs in the guest. See prior [research R6/R7](../001-add-storage-helm-examples/research.md) for the inherited upstream trust boundary, not new live proof.

**Alternatives considered**: Anonymous direct KBS curl, Bitnami sealed secrets, plaintext Helm keys, signature bypass, additional Trustee resources or copied generic token parsers. None are needed or permitted. Requiring pre-created envelope Secrets removes one option/resource without removing any key-delivery mode.

## R5 — Static checks versus “offline” runtime tests

**Decision**: Replace the mixed chart runner with explicit static-only lint/render/parse/source/package checks. Use existing Helm 3.22.0, Python 3.12.12, `PyYAML==6.0.2` and `shellcheck-py==0.11.0.1` pins; a small chart-local checker need not retain pytest. No full test-suite invocation in revised CI.

**Rationale/evidence**: Each `tests/run.sh` executes all pytest tests. Read-only agent classification found:

| Existing content | Classification / disposition |
|---|---|
| `test_render.py`, `test_common_contract.py`, `test_overrides.py`, most `test_isolation.py` | Useful static assertions; adapt only render/package/YAML/source checks. Audit mixed cases before reuse. |
| `test_startup.py`, `test_storage_access.py`, plain `test_format.py` | Mostly workload shell execution with mocked tools/temp files; not static. A few text assertions may be reused independently. |
| Encrypted key/signature/helper/encryption tests | Runtime shell execution, not static or proof of actual attestation/encryption. Exclude from completion invocation. |
| NFS `test_nfs_mount.py` | Runtime shell with mocked mount and GNU-timeout execution; not static. |
| Collection/cleanup/live CLI tests | Python CLI behavior execution; not purely static. |
| `check-images.sh`, prerequisite/live/uninstall tooling | Image/cluster/backend operations; outside completion scope. Inspect before retiring obsolete infrastructure. |

**Alternatives considered**: Continue calling the entire suite “offline”; filter tests by broad filenames without auditing; add live adapters. These violate static-only acceptance or hide missing evidence. Retaining useful historical tools is not authorization to execute them, and revised guides/CI must not depend on them.

## R6 — Ownership, versions and documentation

**Decision**: Keep one owned Recreate Deployment/account/scripts ConfigMap and block claim where applicable. External initdata, pull/key Secrets, NFS server/export/data and Trustee remain unowned. No keep policy or deletion hook; provider Delete reclamation remains a documented usage prerequisite. Bump chart metadata to 0.2.0 during implementation and retain app/image baseline.

**Rationale/evidence**: `templates/pvc.yaml`, `serviceaccount.yaml` and `scc-binding.yaml` already model release-owned objects and account-scoped permission opt-in. Delete/recreate is simple but block uninstall is destructive. The [previous research](../001-add-storage-helm-examples/research.md) and validation records preserve platform/image context without executing new checks.

**Alternatives considered**: Namespace-wide grants, automatic infrastructure setup, backend deletion scripts or upgrade migration tables. These are not required for teaching or static acceptance.

## Gate result

All design unknowns resolved. Pre/post-design constitutional gates pass with no new exception. Corrected trust and hardware/provider capabilities are runtime-use prerequisites, not unresolved planning questions or live completion gates. No new execution evidence is claimed.
