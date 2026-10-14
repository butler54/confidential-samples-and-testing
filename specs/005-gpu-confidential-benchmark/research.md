# Research: GPU Confidential Benchmark (Phase 0)

**Feature**: 005-gpu-confidential-benchmark | **Date**: 2026-10-14

All spec `[NEEDS CLARIFICATION]`-class unknowns were resolved during
clarification (benchmarks: HPL + HPL-MxP; confidential tier: runtime-class
only; GPUs: H100-or-newer). This document records the remaining technical
decisions with rationale and rejected alternatives.

---

## R1: Source of the HPL / HPL-MxP benchmark binaries

**Decision**: Use NVIDIA's already-published **HPC-Benchmarks collection**
container (`nvcr.io/nvidia/hpc-benchmarks`, pinned tag `26.02.01`, carrying
NVIDIA HPL 26.02.01, NVIDIA HPL-MxP 26.02, NCCL 2.29.2 and an
MPICH-ABI-compatible MPI) as the workload image, consumed via an overridable
`images.workload` value. Both benchmarks ship runner helper scripts
(`hpl.sh`, `hpl-mxp.sh`) that generate `HPL.dat` from explicit parameters
(`--n`, `--nb`, `--nprow`, `--npcol`, `--p`, `--q`, affinities) and expect
**one GPU per MPI process**.

**Rationale**: The collection is the vendor-maintained, GPU-optimized
LINPACK-family distribution (based on Netlib HPL and hpl-mxp.org); it is
already published, so constitution IV's "reference an already-published image
where practical" is satisfied directly with no external build step. Pinning
an immutable tag/digest and allowing full-reference overrides covers
disconnected clusters (FR-017).

**Alternatives considered**:
- Build a custom image (perf-utils pattern in `butler54/containers`) wrapping
  the NVIDIA binaries — rejected as the default: unnecessary while NVIDIA
  publishes exactly the needed collection; retained as the **documented
  fallback** for environments where NGC pull authentication is blocked
  (mirror to an externally owned quay namespace, perf-utils pattern).
- Distro-packaged or self-compiled Netlib HPL — rejected: not GPU-optimized,
  and building binaries/images is out of repository scope (constitution IV).
- Using the collection's additional benchmarks (HPCG, STREAM also ship in the
  image) — out of scope for this feature; HPCG noted as a natural future
  candidate for the physics-relevant benchmark (see R9).

## R2: Confidential GPU runtime path on OpenShift

**Decision**: Standard cases run as plain (runc) pods requesting
`nvidia.com/gpu`. Confidential cases run under the OpenShift sandboxed
containers operator's GPU confidential runtime class **`kata-cc-nvidia-gpu`**
(created automatically when NFD + NVIDIA GPU Operator with the CC manager are
installed on H100-or-newer nodes); the non-confidential kata tier
**`kata-nvidia-gpu`** is an optional case where served. Because the
GPU-serving resource name can be `nvidia.com/gpu` or the protected-passthrough
`nvidia.com/pgpu` depending on operator version/configuration, the resource
name is a chart value **auto-detected at preflight** from the node's
allocatable resources and runtime classes (FR-010), never guessed.

**Rationale**: This is the Red Hat-supported confidential-GPU path (GPU
Operator CC manager + OpenShift sandboxed containers), satisfying
constitution III by preferring downstream-supported orchestration; the spec's
default plain-vs-coco case set (assumption) maps one-to-one onto these
runtime classes. No Trustee/attestation integration is included (spec
clarification 2026-10-14).

**Alternatives considered**:
- Upstream CoCo runtime classes (e.g., `kata-qemu-nvidia-gpu-tdx` with
  `nvidia.com/pgpu`) — rejected: upstream path, not the Red Hat-supported
  OpenShift delivery; documented as out of scope.
- kata (non-CC) as a mandatory third tier — rejected: GPU support for the
  plain kata tier is not guaranteed on all target clusters; it stays optional
  per the spec assumption.

## R3: GPU discovery, model gate, and NVLink check (preflight)

**Decision**: Preflight reads NVIDIA GPU Feature Discovery (GFD) node labels:
`nvidia.com/gpu.product` (model gate), `nvidia.com/gpu.count` (count), and
`nvidia.com/nvlink.present` (full-system gate). The model gate applies a
CC-capable allowlist — H100 and newer (H100, H200, B200, GB200,
RTX PRO 6000 Blackwell Server Edition, and successors), extensible via a
runner flag/value — rejecting every other GPU model, including other NVIDIA
models, with an actionable message (FR-002). Missing labels produce a
prerequisite failure that names NFD/GPU Operator installation, never a
guess. GPU-occupancy census (other pods holding the node's GPUs) is
warn-only, mirroring the io-benchmark contract (FR-009).

**Rationale**: GFD labels are the supported discovery surface, require no
privileged debug pod, and exist before any workload is provisioned — exactly
the fail-fast preflight the spec demands.

**Alternatives considered**:
- `oc debug node/` + `nvidia-smi` probing — rejected: privileged, heavier,
  and duplicates what GFD already publishes; the in-pod `nvidia-smi` output
  is still collected as run evidence.
- Trusting user-declared model only — rejected: FR-002 requires detection
  and rejection before provisioning.

## R4: Control-side runner

**Decision**: A new, independent Python 3.12 tool at
`gpu-benchmark/tools/bench.py` (console script `gpu-bench`), mirroring the
approved io-benchmark runner's architecture (preflight → per-case Helm
render/apply → bounded `oc exec` → log collection → parse/normalize →
Markdown + Iceberg emission → deterministic cleanup, including
`--cleanup-only`). Approval is recorded in spec FR-015; deps (pyiceberg,
pyarrow, typer) are declared and pinned in `tools/pyproject.toml` and
lint-validated in CI.

**Rationale**: Constitution I requires the example to be independent of
`io-benchmark`; the orchestration (serial cases, per-case parameters,
verification-aware reporting) exceeds what shell or Helm hooks handle
cleanly, the same rationale accepted for spec 004's runner.

**Alternatives considered**:
- Extending `io-bench` — rejected: violates example independence
  (constitution I) and drags fio/PVC concepts into a GPU harness.
- Shell orchestration — rejected: complexity, per spec 004 precedent.
- Helm-only (Jobs + no runner) — rejected: cannot satisfy serial
  single-pod execution, result collection, comparison reporting (FR-008,
  FR-009).

## R5: Result conventions and surfaces

**Decision**: Mirror io-benchmark exactly: `results/<run-tag>/` containing
`run.env`, `preflight.log`, `manifest-<case>.yaml`, `exec-<case>.log`,
`<case>/` raw HPL/HPL-MxP output per repeat, `LOGS/` pod logs, and
`summary.md`; plus a shared `results/iceberg-warehouse/` with
`runs.metadata`, `runs.case_iterations`, `runs.datapoints`, and
`runs.case_aggregates` tables. The Markdown summary gains one
confidential-vs-standard **delta table** per benchmark × GPU configuration
computed only from verified pairs (FR-007/FR-008).

**Rationale**: Consistency with the repository's established evidence
conventions (SC-005); the same datapoints feed both surfaces so quoted
numbers always trace to the store.

**Alternatives considered**:
- New result format — rejected: needless divergence.
- Cluster-side result storage — rejected: results are control-machine
  artifacts in this repository's pattern; no metrics leave the
  cluster/control machine (spec assumption).

## R6: HPL / HPL-MxP parameter selection

**Decision**: The runner computes the problem size `N` per case to fill
approximately 80% of aggregate GPU memory (`N = sqrt(0.8 × bytes-per-GPU ×
GPU-count / 8)` for fp64 HPL; the HPL-MxP working-set analog), uses NVIDIA's
sample `HPL.dat` block sizes (`NB`) for the detected GPU count as defaults,
and derives the process grid (`P` × `Q`, `P ≤ Q`) from the GPU count.
Parameters are computed **once per run** and reused verbatim for every tier
of the same benchmark/GPU-configuration (FR-004); all overrides
(`--hpl-n`, `--hpl-nb`, …) apply to all tiers alike. The formula, defaults
and quoting rules live in `docs/sizing-guidance.md`; the selection rationale
lives in `docs/benchmark-selection.md` (FR-003).

**Rationale**: A memory-filling `N` produces sustained-peak LINPACK numbers;
deriving it from GPU memory keeps single-GPU and full-system cases
comparable and documented; fixing parameters per run makes tiers directly
comparable.

**Alternatives considered**:
- Fixed small `N` — rejected: measures launch overhead, not sustained
  compute.
- User-supplied parameters only — rejected: no sane default path; defaults
  must exist for SC-005 (README-only reproduction).

## R7: In-pod execution topology

**Decision**: Exactly one benchmark Pod per case. Single-GPU cases request
one GPU and run one MPI process; full-system cases request **all** node GPUs
(count from GFD) in the single Pod and run `mpirun -np <count>` with one GPU
per process (NVIDIA's documented model), using NCCL over NVLink for
inter-GPU communication. CPU/memory requests are sized per MPI process and
exposed as values.

**Rationale**: One pod per case preserves the serial single-pod contract
(FR-009); intra-pod MPI across assigned GPUs is NVIDIA's supported
single-node HPL topology; requesting the full GFD count never silently
benchmarks a subset (US2 scenario 3).

**Alternatives considered**:
- One pod per GPU with cross-pod MPI — rejected: needless scheduling
  complexity; single-node HPL does not need it.
- Multi-node — out of scope per spec assumption.

## R8: Correctness verification and metric parsing

**Decision**: Each benchmark definition (R9) declares a parser mapping that
extracts the performance metric (Gflops) and the HPL residual-check
verification verdict from the benchmark's standard output. A case counts as
a performance result **only if verified**; unverified or failed checks mark
the iteration invalid and exclude it from comparisons and deltas (FR-007,
SC-003). HPL (fp64) and HPL-MxP (mixed) metrics are never compared to each
other — deltas are computed within one benchmark only.

**Rationale**: The LINPACK residual check is the benchmarks' own built-in
correctness proof; reusing it avoids re-implementing numerical verification.

**Alternatives considered**:
- Recompute residuals in the runner — rejected: duplicates binary behavior
  with no added trust.
- Report unverified numbers with a flag — rejected: violates SC-003
  ("never presented as performance results").

## R9: Benchmark catalog extensibility (FR-012)

**Decision**: Benchmarks are **declarative YAML definitions** in
`gpu-benchmark/benchmarks/` (`hpl.yaml`, `hpl-mxp.yaml`). A definition
declares: id, precision label, parameter generation inputs, command template,
parser mapping (metric + verification), and documentation reference. The
runner discovers definitions at startup; adding a benchmark (e.g., the
anticipated physics-relevant one) is adding one YAML file plus its docs — no
change to the chart, runner core, or reporting (SC-004). The contract is
specified in [contracts/benchmark-catalog.md](contracts/benchmark-catalog.md).

**Rationale**: Declarative data files keep the catalog script-free
(constitution II — no new scripts need approval to add a benchmark) and make
the extensibility claim mechanically testable.

**Alternatives considered**:
- Python-plugin benchmarks — rejected: each new benchmark would be an
  unapproved script (constitution II).
- Hardcoded two benchmarks — rejected: violates FR-012/SC-004.

## R10: Single-GPU assignment recording

**Decision**: Single-GPU cases request exactly one GPU via the detected
resource; the assigned device identity (as reported by in-pod `nvidia-smi`)
is captured in the case's raw evidence and result record. Where the serving
device plugin honors explicit index selection (`NVIDIA_VISIBLE_DEVICES`),
an optional value can pin the index; the default accepts the plugin's
assignment and records it.

**Rationale**: Kata/CC GPU passthrough does not guarantee deterministic
index selection across tiers; recording the assignment satisfies FR-005's
explicit-selection intent (the pod uses exactly one, known GPU) without
promising an index the runtime cannot honor identically in both tiers —
which would itself break comparability (FR-004).

**Alternatives considered**:
- Mandatory index pinning — rejected: not portable across plain/kata-cc
  device-plugin behavior; risks incomparable tiers.

---

## Future-work note (not in scope)

The NVIDIA HPC-Benchmarks collection also ships **HPCG** (sparse
PDE-conjugate-gradient benchmark) — a strong candidate for the anticipated
physics-relevant (non-AI) benchmark, addable under the R9 catalog contract
without harness changes. Recorded for the future feature; explicitly out of
scope here.
