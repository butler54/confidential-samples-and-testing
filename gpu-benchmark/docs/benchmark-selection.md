# Benchmark selection: why HPL and HPL-MxP own every number here

**Feature**: 005-gpu-confidential-benchmark | **Decision record per FR-003**

Tool selection was a deliberate decision, not inertia. This document records
why the first release runs **NVIDIA HPL** (double-precision LINPACK) and
**NVIDIA HPL-MxP** (mixed-precision LINPACK), and states exactly what would
change the decision.

## Selection

| Benchmark | Precision | What it exercises | Why it is in the first release |
|---|---|---|---|
| NVIDIA HPL 26.02.01 | fp64 | Dense LU solve: DGEMM-bound compute + inter-GPU communication (NCCL over NVLink) | The canonical "fundamental" GPU compute benchmark (Netlib HPL, GPU-optimized by NVIDIA); the TOP500 metric; directly comparable fp64 Gflops across runtime classes |
| NVIDIA HPL-MxP 26.02 | mixed (Tensor Cores) | Same dense solve using mixed-precision iteration with fp64 refinement | The modern HPL successor (hpl-mxp.org); stresses Tensor Core paths whose confidential-mode behavior may differ from fp64 vector units |

Both ship in the **NVIDIA HPC-Benchmarks collection** container
(`nvcr.io/nvidia/hpc-benchmarks:26.02.01`, including NCCL 2.29.2 and an
MPICH-ABI-compatible MPI), which is the vendor-maintained, already-published
distribution of both binaries (constitution IV: this repository defines and
builds zero container images; research R1).

## Requirements driving the choice

- **Spec FR-003**: first release includes both classic double-precision HPL
  and mixed-precision HPL-MxP (clarification 2026-10-14).
- **FR-004**: identical parameters across runtime classes — both benchmarks
  take fully declarative parameters (`N`, `NB`, `P`, `Q`) that the runner
  computes once per run and reuses verbatim for plain and confidential cases.
- **FR-007**: explicit correctness verification — both binaries perform the
  standard LINPACK residual check and print a `PASSED`/`FAILED` verdict the
  harness parses and gates on.
- **FR-006**: full-system multi-GPU — both expect one GPU per MPI process
  (`mpirun -np <gpus>`), which is exactly the single-pod all-GPU topology.

## Alternatives considered

- **NVIDIA HPCG** (also in the collection): sparse conjugate-gradient,
  memory-bound; a strong candidate for the anticipated physics-relevant
  benchmark, deliberately **not** selected for the fundamental-first scope
  (see `benchmarks/README.md`).
- **NVIDIA STREAM** (also in the collection): memory-bandwidth microbenchmark,
  not a compute benchmark; out of the fundamental-LINPACK scope.
- **Self-compiled Netlib HPL / distro packages**: not GPU-optimized and would
  require building binaries/images in this repository (constitution IV).
- **GPU AI/ML benchmarks** (e.g., MLPerf-style training): explicitly out of
  scope per the spec (non-goal; the extensibility requirement exists for a
  physics-relevant, non-AI benchmark).

## What would change this decision

- NVIDIA stops publishing the HPC-Benchmarks collection, or the residual-check
  output format changes in a way the catalog parser mapping cannot express —
  the parser is declarative per benchmark definition
  (`benchmarks/*.yaml`), so format drift is absorbed by editing data, not code.
- A Red Hat-supported GPU LINPACK distribution appears (constitution III
  downstream-first preference would then apply).
- The future physics benchmark feature lands: HPCG (or similar) is added
  under the catalog contract — HPL/HPL-MxP stay untouched.

## Runtime notes carried by the definitions

- The container's `hpl.sh` / `hpl-mxp.sh` helper scripts generate `HPL.dat`
  from explicit parameters and launch MPI internally; the catalog command
  templates call them from the collection's workspace directory.
- OpenMPI in the container runs as root (pod default); the runner exports
  `OMPI_ALLOW_RUN_AS_ROOT=1` / `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1` for the
  exec calls.
- NGC pull authentication: if the target cluster cannot pull from `nvcr.io`,
  mirror the pinned image to an externally owned registry and pass
  `--workload-image <full-reference>` (FR-017); the fallback mirror is owned
  outside this repository (perf-utils pattern, research R1).
