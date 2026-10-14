# Implementation Plan: GPU Confidential Benchmark

**Branch**: `005-gpu-confidential-benchmark` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-gpu-confidential-benchmark/spec.md` (clarified 2026-10-14: HPL + HPL-MxP both in first release; confidential tier is runtime-class only, no Trustee integration; H100-or-newer GPUs only)

## Summary

Deliver a self-contained `gpu-benchmark/` example consisting of (a) an
**explicitly-approved local Python tool** (`gpu-benchmark/tools/bench.py`,
console script `gpu-bench`, run on the operator's control machine) that, for a
single operator invocation, runs the LINPACK-family benchmark cases
(NVIDIA HPL double-precision and NVIDIA HPL-MxP mixed-precision) across
standard (plain) and confidential (`kata-cc-nvidia-gpu`) pods, in single-GPU
and full-system (all node GPUs over NVLink) configurations, strictly serially
on one nominated H100-or-newer node — preflight (GPU model/count/NVLink/
runtime-class/image gates via GPU-Feature-Discovery node labels), Helm chart
render/apply per case, in-pod MPI execution via bounded `oc exec`, raw-output
collection, result parsing with HPL residual-check verification, Markdown
comparison summary emission, and Apache Iceberg appends to a local warehouse;
(b) one Helm chart that renders each case's benchmark Pod; and (c) the
externally published NVIDIA HPC-Benchmarks collection image
(`nvcr.io/nvidia/hpc-benchmarks`, pinned) as the workload image carrying HPL,
HPL-MxP, MPI and NCCL — this repository defines and builds zero container
images (FR-011, constitution IV).

## Technical Context

**Language/Version**: Python 3.12 for the approved control-side tool (pinned deps:
PyIceberg, PyArrow, Typer); Helm 3 (chart apiVersion v2); in-pod: NVIDIA HPL 26.02.01
and HPL-MxP 26.02 from the pinned `nvcr.io/nvidia/hpc-benchmarks:26.02.01` image
(includes NCCL 2.29.2 and MPICH-ABI-compatible MPI)

**Primary Dependencies**: `helm`, `oc`, Python 3.12 + `pyiceberg`/`pyarrow`/`typer`
(declared+pinned in `gpu-benchmark/tools/pyproject.toml`); in-pod NVIDIA HPC-Benchmarks
binaries (HPL, HPL-MxP) with their bundled MPI + NCCL — all in-pod binaries come from
the externally published NVIDIA image; no image is defined or built by this repository

**Storage**: N/A in-cluster — no PVCs; benchmark working set lives in GPU memory;
results land on the control machine in `<results-root>/<run-tag>/` plus a shared
Iceberg warehouse `<results-root>/iceberg-warehouse/` (mirrors io-benchmark
conventions, FR-008)

**Testing**: Repository-standard lint pipeline (`helm lint --strict`,
`values.schema.json` validation, `python3 -m py_compile`, `shellcheck` for
`tests/run.sh`) — benchmark correctness is the operator's live observation of
verified results per FR-007/SC-003

**Target Platform**: Red Hat OpenShift on bare metal with NVIDIA H100-or-newer
GPUs; NFD + NVIDIA GPU Operator (with CC manager for GPU confidential-computing
mode) and OpenShift sandboxed containers operator providing the
`kata-cc-nvidia-gpu` (confidential) and `kata-nvidia-gpu` (kata) runtime
classes; standard cases run as plain pods with `nvidia.com/gpu`; control
machine is the operator's workstation with `oc`/`helm`/Python 3.12

**Project Type**: Self-contained example directory (chart + approved Python
tool + docs + benchmark catalog), matching repo ensemble conventions

**Performance Goals**: Not a service SLO feature; measured outcomes are HPL
(fp64 Gflops) and HPL-MxP (mixed-precision Gflops) per case with explicit
residual-check verification, and the confidential-vs-standard delta per
benchmark × GPU configuration

**Constraints**: H100-or-newer GPUs only (FR-002); strictly serial cases, at
most one benchmark pod existing at any time, no cordon/drain/evict (FR-009);
identical benchmark parameters across runtime classes (FR-004); airgap-safe
(immutable image override, no startup downloads, FR-017); no in-repo container
definitions (constitution IV); scripts only with explicit approval
(constitution II — approval recorded in spec FR-015)

**Scale/Scope**: 2 benchmarks × 2 core tiers (plain, coco; kata optional where
served) × 2 GPU configurations (single, full-system) = up to 8–12 cases per
invocation; one node per invocation; results accumulate as Iceberg appends
across invocations

## Constitution Check (v2.0.0)

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Evaluation |
|---|---|---|
| I. Self-Contained Examples | PASS | New `gpu-benchmark/` directory holds chart, values, catalog, approved tool, docs, tests; sibling examples untouched; staging samples untouched |
| II. Helm-First Delivery | PASS | Case workload is a Helm chart with comprehensive `values.yaml` + JSON schema; the one script (Python control tool) is explicitly approved in advance, recorded in spec FR-015 (session 2026-10-14), with documented rationale — serial case orchestration, per-case render/apply, bounded exec, log collection and dual-surface result emission exceed what shell or chart hooks handle cleanly; benchmark definitions are declarative data files (YAML), not scripts |
| III. Downstream-First Dependencies | PASS (documented) | The NVIDIA GPU stack (GPU Operator, CC manager), NVIDIA HPC-Benchmarks image, PyIceberg/PyArrow/Typer have no Red Hat-supported equivalents for GPU LINPACK benchmarking; justification recorded in README + research R1/R2/R4 |
| IV. No Container Definitions | PASS | Repository defines/builds zero container images; the workload image is NVIDIA's already-published, pinned `nvcr.io/nvidia/hpc-benchmarks` collection, consumed by overridable value with ownership documented in README (FR-011); a documented mirror fallback (externally owned quay namespace, perf-utils pattern) covers NGC-pull-auth environments |
| V. CI/CD and Version Discipline | PASS | Chart added to the existing CI lint matrix; pinned image tag and `tools/pyproject.toml` declarations; version changes reviewed in artifact metadata |
| VI. Simplicity and Explainability | PASS | Chart + one tool + declarative benchmark catalog + docs; every component justified in research.md; smallest design that demonstrates confidential-GPU benchmark comparison |

No violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/005-gpu-confidential-benchmark/
├── plan.md              # This file
├── research.md          # Phase 0: benchmark/runtime/discovery decisions (FR-003, FR-011)
├── data-model.md        # Phase 1: run/case/result/comparison entities
├── quickstart.md        # Phase 1: validation runbook
├── contracts/
│   ├── operator-surface.md      # gpu-bench CLI surface and exit codes
│   └── benchmark-catalog.md     # FR-012 contract for adding benchmarks
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
gpu-benchmark/
├── Chart.yaml                    # Helm chart (apiVersion v2)
├── values.yaml                   # case, node, gpu config, runtime class, image, benchmark params
├── values.schema.json            # validated input contract
├── README.md                     # prerequisites, ownership, running, interpreting (FR-016)
├── docs/
│   ├── benchmark-selection.md    # HPL + HPL-MxP selection rationale (FR-003)
│   └── sizing-guidance.md        # problem-size (N) computation and quoting rules
├── templates/
│   ├── pod.yaml                  # benchmark Pod (runtimeClassName, GPU resources)
│   ├── configmap-hpl-dat.yaml    # rendered HPL.dat / HPL-MxP inputs per case
│   └── NOTES.txt
├── tests/
│   ├── requirements.txt
│   └── run.sh                    # helm lint --strict + schema validation (CI)
├── benchmarks/                   # declarative benchmark catalog (FR-012)
│   ├── hpl.yaml
│   └── hpl-mxp.yaml
└── tools/
    ├── pyproject.toml            # pinned deps; gpu-bench console script
    └── bench.py                  # approved control-side runner (FR-015)
```

**Structure Decision**: Single self-contained example directory at repository
root, mirroring the proven `io-benchmark/` layout (chart + values + schema +
docs + tests + approved tools) with two additions justified by this feature:
`benchmarks/` (declarative catalog required by FR-012) and
`configmap-hpl-dat.yaml` (HPL parameter rendering). No storage templates —
the GPU benchmark has no PVC (working set is GPU memory). No `src/`, `tests/`
at root, or shared framework (constitution I, VI).

## Complexity Tracking

> No constitution violations — nothing to justify.
