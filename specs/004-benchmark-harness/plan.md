# Implementation Plan: IO Benchmark Harness for Confidential Pods

**Branch**: `004-benchmark-harness` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-benchmark-harness/spec.md` (updated 2026-10-13
post-constitution-v2.0.0: FR-017 no in-repo images, FR-018 approved local Python tool)

## Summary

Deliver a self-contained `io-benchmark/` example consisting of (a) an **explicitly-approved local
Python tool** (`tools/bench.py`, run on the operator's control machine) that, for a single operator
invocation, runs up to six workload cases (plain/kata/coco × unencrypted/LUKS) strictly serially on
one nominated node — preflight, Helm chart render/apply per case, per-repeat fio execution inside the
benchmark pod via bounded `oc exec`, raw-log collection, result parsing/normalization, Markdown
summary emission, and Apache Iceberg appends (via pinned PyIceberg+PyArrow) to a local warehouse;
(b) one Helm chart that renders each case's Pod + raw-block PVC; and (c) fio as the analyzed-and-
selected benchmark (research R1 — fio over sysbench/dbench) executed **inside** the benchmark pod,
which runs the existing externally-built `quay.io/rh-ee-chbutler/perf-utils` image (FR-017 — this
feature defines/builds zero container images).

## Technical Context

**Language/Version**: Python 3.12 for the approved control-side tool (pinned deps: PyIceberg, PyArrow);
Helm 3 (chart apiVersion v2); fio 3.x inside benchmark pods (from the perf-utils image)

**Primary Dependencies**: `helm`, `oc`, Python 3.12 + `pyiceberg`/`pyarrow`/`typer` (declared+pinned
in `tools/pyproject.toml`),
fio 3.x, xfsprogs + cryptsetup in pod (encrypted cases) — all in-pod binaries come from the existing
`quay.io/rh-ee-chbutler/perf-utils` image; no image is defined or built by this repository

**Storage**: N/A in-repo — dynamically provisioned raw-block PVCs per case (volumeMode: Block), XFS
(plain) or LUKS+XFS (encrypted) prepared guest-side inside the pods; local run folder
`<results-root>/<run-id>/` + shared Iceberg warehouse `<results-root>/iceberg-warehouse/`

**Testing**: Repository-standard lint pipeline (`helm lint --strict`, `shellcheck` where shell remains,
`sh -n`, `python3 -m py_compile`) — correctness of benchmarks is the operator's live observation per
spec FR-009/FR-012

**Target Platform**: Red Hat OpenShift on bare metal (Intel TDX for coco cases), coco-pattern runtime
classes (`kata`, `kata-cc`); control machine is the operator's workstation with `oc`/`helm`/Python 3.12

**Project Type**: Self-contained example directory (chart + approved Python tool + docs), matching
repo ensemble conventions

**Performance Goals**: Not a service SLO feature; instead: broad characterized spectrum (bs 4k→1M,
seq+rand, read/write/mixed), direct IO, volume ≥ node RAM + margin (warn-only violation path),
N-repeat spread reporting

**Constraints**: airgap-safe (image override input, no downloads), OpenShift SCC-compatible, strictly
serial pod scheduling, no in-repo container definitions (constitution v2.0.0 IV), scripts only with
explicit approval (constitution v2.0.0 II — approval recorded in spec Clarifications)

**Scale/Scope**: 6 cases per invocation; one node per invocation; results accumulate as Iceberg
appends across invocations

## Constitution Check (v2.0.0)

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Evaluation |
|---|---|---|
| I. Self-Contained Examples | PASS | New `io-benchmark/` directory holds chart, approved tool, docs, tests; sibling examples untouched; staging samples untouched |
| II. Helm-First Delivery | PASS | Case workload is a Helm chart with comprehensive values; the one script (Python control tool) is explicitly approved in advance, recorded in spec Clarifications (session 2026-10-13 post-v2.0.0), with documented rationale — the workflow's serial repeat/exec/log-collection complexity exceeds what shell orchestration handles cleanly |
| III. Downstream-First Dependencies | PASS (documented) | fio/PyIceberg are upstream community tools with no Red Hat-supported equivalents; justification recorded in README + research R1/R3 |
| IV. No Container Definitions | PASS | Repository defines/builds zero container images; the single in-cluster tooling image is the already-published, externally-built `quay.io/rh-ee-chbutler/perf-utils`, consumed by overridable value with ownership documented in README (FR-017) |
| V. CI/CD and Version Discipline | PASS | Chart added to the existing CI matrix; pinned versions and `tools/pyproject.toml` declaration |
| VI. Simplicity and Explainability | PASS | Chart + one tool + docs; every component justified in research.md |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/004-benchmark-harness/
├── plan.md              # This file
├── research.md          # Phase 0: tool analysis (US1/FR-011 deliverable) + design decisions
├── data-model.md        # Phase 1: run/case/datapoint/summary/iceberg entities
├── quickstart.md        # Phase 1: validation runbook
├── contracts/
│   ├── operator-surface.md      # CLI + env + run-folder + exit-code contract
│   └── runtime-and-validation.md# What validation proves vs explicitly does not
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
io-benchmark/
├── Chart.yaml                       # single case chart
├── values.yaml / values.schema.json
├── templates/
│   ├── pvc.yaml               # raw-block volume claim (per case)
│   ├── pod.yaml               # benchmark pod: node pin, runtimeClass, LUKS init (encrypted), exec-driver main
│   ├── configmap-fio-job.yaml # operator-overridable job file
│   └── NOTES.txt
├── tools/
│   ├── bench.py               # approved single Python entrypoint: preflight → serial cases → summarize
│   └── pyproject.toml         # declared+pinned deps (pyiceberg/pyarrow/typer), io-bench console script
├── docs/
│   ├── benchmark-selection.md # US1/FR-011: fio vs sysbench vs dbench analysis
│   └── sizing-guidance.md     # FR-005/FR-012: cache-defeat sizing + variance interpretation
├── tests/
│   └── run.sh                 # helm lint --strict + shellcheck + sh -n + py_compile
└── README.md                  # prerequisites, image-ownership note, runbook, outputs, cleanup

README.md                              # root index gains io-benchmark row + analysis pointer
.github/workflows/validate-examples.yml  # matrix extended to io-benchmark
```

**Structure Decision**: One self-contained example directory at repo root following ensemble
conventions. Exactly one approved script (`tools/bench.py`) per constitution v2.0.0 II — the
serial case lifecycle, per-repeat `oc exec` driving, JSON collection, normalization, Markdown
rendering, and PyIceberg appends are one coherent control flow; splitting it across shell scripts
plus a second language would duplicate process management. Previously-envisioned external
`fio`/`fio-summarizer` images are eliminated: in-pod binaries come from the existing
`perf-utils` image and summarization moved into the approved tool. `staging/fio-script/` remains
untouched reference material.

## Phase 0 — Research

See [research.md](research.md). Headline decisions:

1. **Tool selection (R1, US1/FR-011)**: **fio** selected as the sole end-to-end tool. Purpose-built
   block/filesystem benchmark, JSON output, direct-IO and bs-range control, async engines for
   queue-depth scaling, actively maintained. sysbench `fileio` rejected (no raw-device mode, coarser
   control, text-only output). dbench rejected (SMB protocol load generator — all wrap/fork
   permutations misaligned with block-device goals). sysbench/dbench documented as future
   cross-check candidates (sysbench is coincidentally also in the perf-utils image).
2. **Execution model (R2/R5)**: fio runs inside the benchmark pod via bounded `oc exec` invocations
   driven by the approved Python tool, one invocation per repeat (default 3); pod main process idles
   so each repeat is independently timed and failures isolate per-repeat.
3. **Summarization (R3)**: the approved Python tool parses fio `--output-format=json` per repeat per
   section, computes per-datapoint spread (min/max/stddev), renders the Markdown table, and appends
   to local Iceberg tables (SQL-catalog-on-SQLite, warehouse in a local folder). No containerized
   summarizer (FR-018 supersedes any image-based post-processing from earlier drafts of this plan).
4. **Images (R-new)**: the only container image anywhere in the feature is the existing, externally-
   built `quay.io/rh-ee-chbutler/perf-utils` (FR-017/constitution v2.0.0 IV). It ships fio 3.42+,
   xfsprogs, and cryptsetup — the complete in-pod toolset.
5. **Encryption parity (R6)**: encrypted cases reuse the guest-side LUKS+XFS topology from the
   block-storage-encrypted example (init container formats/unlocks and leaves an activated dm-crypt
   device + XFS);
   demonstration-grade static key per spec assumption; no attestation (steady-state IO unaffected).
6. **Cache-defeat (R7)**: fio `direct=1`, volume ≥ node RAM + margin evaluated preflight with
   warn-only + cache-suspect stamping path (spec clarification).
7. **Isolation & cleanliness (R8/R9)**: preflight tenant census warns only; serial case loop
   guarantees one pod at a time; trap-based cleanup + deterministic rerun recovery instructions.

## Phase 1 — Design

1. **Entities**: see [data-model.md](data-model.md) — run identity, case catalog (exact six names),
   repeat-level datapoints, aggregates, run-folder layout, Iceberg table schemas
   (`runs.metadata`, `runs.case_iterations`, `runs.datapoints`, `runs.case_aggregates`).
2. **Contracts**: see [contracts/operator-surface.md](contracts/operator-surface.md)
   (CLI/env/outputs) and [contracts/runtime-and-validation.md](contracts/runtime-and-validation.md)
   (validation boundary).
3. **Validation guide**: see [quickstart.md](quickstart.md).

### Constitution Check (post-design, v2.0.0)

All six principles re-evaluated PASS post-design. The single Python script carries its recorded
explicit approval; zero container definitions exist in-repo. No complexity-tracking entries.
