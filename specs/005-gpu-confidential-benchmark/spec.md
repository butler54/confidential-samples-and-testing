# Feature Specification: GPU Confidential Benchmark

**Feature Branch**: `005-gpu-confidential-benchmark`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Add a new benchmark which is designed to exercise the performance of GPUs in confidential containers and compare with GPUs in standard containers. 1. Only support NVIDIA GPUs. 2. First scope is fundamental benchmarks such as LINPACK (on GPUs). 3. Anticipate adding a benchmark that is a physics (not AI) relevant benchmark in the future. 4. Also support single GPUs or full system (4 or 8 GPUs, connected via NVLink)."

## Clarifications

### Session 2026-10-14

- Q: Which LINPACK-family benchmark should be the first catalog entry for the GPU comparison? → A: Both classic HPL (double-precision) and HPL-MxP (mixed-precision) ship in the first release.
- Q: Must the confidential benchmark cases demonstrate attestation (retrieving a secret from the cluster Trustee), or only run under the confidential runtime class? → A: Runtime-class only — no Trustee/attestation integration in this example.
- Q: Which NVIDIA GPUs must the example support in its first release? → A: H100 or newer only — these are the only models supporting confidential GPUs; preflight rejects all other GPU models.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single-GPU fundamental benchmark, confidential vs standard (Priority: P1)

A platform engineer wants to quantify what confidential containers cost in raw GPU
compute. Using one nominated node with at least one NVIDIA GPU, they run the
fundamental GPU compute benchmarks from the LINPACK family (dense linear
algebra: HPL and HPL-MxP) with identical benchmark parameters per benchmark:
once in a standard container pod and
once in a confidential container pod. Each run produces a performance number
together with an explicit numerical-correctness verification, and the harness
presents the two numbers side by side with their delta.

**Why this priority**: This is the core question of the feature — the
confidential-vs-standard performance delta on the most fundamental GPU benchmark.
Everything else (multi-GPU, future benchmarks) builds on this capability.

**Independent Test**: Can be fully tested by running the single-GPU benchmark in
both pod types on one NVIDIA GPU node and inspecting the resulting comparison
report; it delivers standalone value as a confidential-container GPU cost
measurement.

**Acceptance Scenarios**:

1. **Given** a nominated node with at least one NVIDIA GPU and both standard and
   confidential runtime support available, **When** the engineer runs the
   benchmark in single-GPU mode, **Then** it completes for both the standard and
   the confidential pod, reports a correctness-verified performance number for
   each, and presents the confidential-vs-standard delta.
2. **Given** a node without NVIDIA GPUs, **When** the run is attempted,
   **Then** it fails fast during preflight with a clear prerequisite message
   before any workload is provisioned.
3. **Given** the confidential pod cannot start or cannot access the GPU
   (for example attestation or device assignment failure), **When** the run is
   attempted, **Then** the failure is reported distinctly as an environment or
   attestation problem and never presented as a benchmark performance result.
4. **Given** a benchmark execution whose numerical result fails its correctness
   verification, **When** results are reported, **Then** that run is marked
   invalid and excluded from the performance comparison.

---

### User Story 2 - Full-system multi-GPU benchmark (Priority: P2)

A platform engineer wants to measure whole-system GPU throughput: all NVIDIA GPUs
on the nominated node (typical configurations of 4 or 8 GPUs connected via
NVLink) working together on one benchmark problem, again comparing confidential
against standard containers with identical parameters.

**Why this priority**: Full-system runs exercise inter-GPU communication
(NVLink), which is where confidential-container overhead may differ most from
single-GPU compute; it is the second half of the fundamental-benchmark scope but
depends on the single-GPU machinery from User Story 1.

**Independent Test**: Can be fully tested by running the full-system benchmark
on a multi-GPU NVLink node in both pod types and inspecting the comparison
report; it delivers standalone value as a whole-system confidential-container
GPU cost measurement.

**Acceptance Scenarios**:

1. **Given** a nominated node with 4 or 8 NVIDIA GPUs connected via NVLink,
   **When** the engineer runs the benchmark in full-system mode, **Then** the
   benchmark uses all GPUs on the node in a single benchmark process set,
   completes for both standard and confidential pods, and reports the
   correctness-verified multi-GPU result and confidential-vs-standard delta.
2. **Given** a full-system run is requested but the node's GPUs are not
   NVLink-connected, **When** preflight runs, **Then** the full-system case is
   rejected with a clear explanation of the topology requirement.
3. **Given** a full-system run is requested on a node with fewer GPUs than the
   engineer's declared expectation, **When** preflight runs, **Then** the harness
   reports the actual GPU count and either proceeds with all available GPUs or
   stops for confirmation, but never silently benchmarks a subset while claiming
   a full-system result.

---

### User Story 3 - Add a future physics-relevant benchmark (Priority: P3)

A maintainer wants to add a second benchmark — a physics-relevant (not AI)
workload — without redesigning the harness. They add a new benchmark definition
alongside the LINPACK-family benchmark; the existing benchmark definitions,
deployment structure, execution flow, and reporting are unchanged, and the new
benchmark automatically participates in the same confidential-vs-standard
comparison.

**Why this priority**: The first scope is fundamental benchmarks only, but the
design must not paint the feature into a corner; extensibility is anticipated
but not delivered as a benchmark in this feature.

**Independent Test**: Can be tested by adding a placeholder benchmark definition
and confirming the harness discovers, runs, and reports it through the same flow
without any change to the existing definitions or reporting.

**Acceptance Scenarios**:

1. **Given** the delivered harness with the LINPACK-family benchmarks,
   **When** a maintainer adds a new benchmark definition to the catalog,
   **Then** it runs and is reported through the same cases, verification, and
   comparison flow with no modification to existing benchmark definitions.
2. **Given** the benchmark catalog, **When** a user selects which benchmarks to
   run, **Then** the selection includes the LINPACK-family benchmark and any
   subsequently added benchmarks, and unselected benchmarks have no effect on
   the run.

---

### Edge Cases

- What happens when the nominated node has no NVIDIA GPUs or the GPU device
  plugin is not serving them? Preflight must fail fast with an actionable
  prerequisite message.
- What happens when the node has NVIDIA GPUs older than the H100 generation?
  Preflight must reject the run with a clear statement of the
  H100-or-newer requirement (confidential-GPU support), before any workload
  is provisioned.
- What happens when the requested GPU count for a full-system run exceeds what
  the node provides? The harness must surface the actual count and never report
  a partial run as a full-system result.
- What happens when the confidential runtime class is missing or the
  confidential pod cannot obtain the GPU? The case must be reported as an
  environment/attestation failure, distinct from performance results.
- What happens when another tenant workload is using the GPUs during a run?
  The harness must census-warn about potential contamination (it never cordons
  or evicts; isolation is the engineer's responsibility, mirroring the
  io-benchmark contract).
- What happens when the benchmark's numerical result fails correctness
  verification? The run must be marked invalid and excluded from comparisons.
- What happens when the same GPU model differs across candidate nodes? All
  cases of one run must execute on one nominated node so results are comparable.
- What happens in a disconnected (airgapped) cluster? The workload image must
  be supplied by full immutable-reference override with no startup downloads.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The example MUST be self-contained in its own directory (chart,
  values, documentation, tests) and MUST NOT depend on files or implicit setup
  from a sibling example (constitution I).
- **FR-002**: The benchmark MUST support NVIDIA GPUs of the H100 generation or
  newer only — these are the only models with confidential-GPU support.
  Preflight MUST detect and reject runs targeting nodes with any other GPU
  model, including other NVIDIA GPUs, before any workload is provisioned.
- **FR-003**: The first release MUST include two fundamental GPU compute benchmarks
  from the LINPACK family: classic double-precision HPL and mixed-precision
  HPL-MxP. The exact variants, versions, and parameter sets MUST be documented
  in a benchmark-selection rationale within the example, mirroring the
  io-benchmark fio decision record.
- **FR-004**: The harness MUST execute every benchmark case with identical
  benchmark parameters across runtime classes so confidential and standard
  results are directly comparable.
- **FR-005**: The harness MUST support single-GPU execution: one NVIDIA GPU
  assigned to the benchmark pod, explicitly selected on multi-GPU nodes.
- **FR-006**: The harness MUST support full-system execution: all NVIDIA GPUs
  on the nominated node (typical configurations of 4 or 8 GPUs connected via
  NVLink) participating in one benchmark execution that exercises inter-GPU
  communication.
- **FR-007**: Every benchmark result MUST carry an explicit numerical
  correctness verification (for LINPACK-family benchmarks, the standard residual
  check); runs that fail verification MUST be marked invalid and excluded from
  performance comparisons.
- **FR-008**: The harness MUST produce per-case results and a side-by-side
  confidential-vs-standard comparison for each benchmark and GPU configuration,
  in a human-readable report and in structured, self-describing local tables,
  consistent with the io-benchmark example's result conventions.
- **FR-009**: Cases MUST run serially with at most one benchmark pod existing
  at any time, on one nominated node per run; the harness MUST NOT cordon,
  drain, or evict anything (census warnings only).
- **FR-010**: Preflight MUST verify, before provisioning: NVIDIA GPU presence
  and count, runtime class availability for selected cases, NVLink
  interconnect topology for full-system cases, and workload image
  availability; every failure MUST produce an actionable message.
- **FR-011**: The workload image containing the GPU benchmark binaries MUST be
  built and published outside this repository and referenced by immutable
  reference, overridable for mirrors and disconnected operation; this
  repository MUST NOT define or build container images (constitution IV), and
  the image's ownership and approval MUST be documented in the example README.
- **FR-012**: Benchmark definitions MUST be structured as a catalog such that
  adding a benchmark (for example a future physics-relevant, non-AI benchmark)
  requires adding a new definition only, with no modification to existing
  benchmark definitions, the chart, or the reporting flow.
- **FR-013**: The workload MUST be delivered as a Helm chart exposing
  environment-specific and operational configuration through a comprehensive
  `values.yaml` (constitution II).
- **FR-014**: Non-Red Hat dependencies (the NVIDIA GPU stack, GPU benchmark
  binaries, the workload image) MUST be explicitly justified in the example
  documentation, including why an equivalent downstream resource cannot satisfy
  the requirement (constitution III).
- **FR-015**: Any control-side runner tooling required to orchestrate cases and
  collect results is explicitly approved by this specification, subject to the
  same constraints as the approved io-benchmark runner: simplest practical
  language, lint-validated in CI, and a documented rationale for why the
  behavior cannot live in a Helm chart or manifests (constitution II).
- **FR-016**: The example MUST document its target OpenShift prerequisites
  (NVIDIA GPU operator or equivalent device plugin, GPU-capable confidential
  runtime class, bare-metal GPU node), required confidential-computing
  capabilities, and expected verification outcome.
- **FR-017**: The harness MUST support disconnected operation by accepting
  full immutable image-reference overrides without any startup package
  downloads.

### Key Entities *(include if feature involves data)*

- **Benchmark**: A catalog entry identifying a GPU workload (first entries:
  classic double-precision HPL and mixed-precision HPL-MxP dense linear
  algebra), its version, its tunable parameters, and its
  correctness-verification method.
- **Benchmark Case**: One combination of benchmark, runtime class (standard or
  confidential), and GPU configuration (single-GPU or full-system) — the unit
  of execution and measurement.
- **Benchmark Run**: One serial execution of a selected set of cases on one
  nominated node under a run tag, producing one report.
- **Result Record**: The outcome of one case: performance metric, correctness
  status, and the environment it was measured in (GPU model and count,
  runtime class, benchmark parameters).
- **Comparison Report**: The side-by-side presentation of confidential vs
  standard result records per benchmark and GPU configuration, including the
  performance delta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete single-GPU comparison run (standard plus confidential
  cases) finishes on a suitably provisioned node and yields a
  correctness-verified performance number for each runtime class plus the
  explicit delta between them.
- **SC-002**: A full-system comparison run on a 4- or 8-GPU NVLink node
  finishes for both runtime classes and yields correctness-verified multi-GPU
  results plus the delta.
- **SC-003**: 100% of reported performance numbers carry an explicit
  correctness-verification status; unverified or failed runs are never
  presented as performance results.
- **SC-004**: Adding a new benchmark to the catalog requires adding a
  benchmark definition only — zero modifications to existing benchmark
  definitions, the chart structure, or the reporting flow.
- **SC-005**: A platform engineer can deploy, run, and interpret the example
  using only its own README and reproduce a comparison run on a second
  suitably provisioned cluster.
- **SC-006**: All repository linting and validation passes for the example,
  and any control-side runner added is lint-validated in CI.

## Assumptions

- The target environment is a bare-metal OpenShift cluster with confidential
  containers (a GPU-capable confidential runtime class) and NVIDIA H100-or-newer
  GPUs already served by the NVIDIA GPU operator or an equivalent device
  plugin; these are prerequisites documented by the example, not delivered by
  it.
- The default case set compares standard (plain) pods against confidential
  (coco) pods, mirroring the repository's io-benchmark tier pattern; an
  intermediate kata (non-confidential) tier is included only where GPU support
  for it exists, and its absence must not block the core comparison.
- The exact problem parameters for both first-release benchmarks (HPL and
  HPL-MxP) are selected during planning and recorded in a benchmark-selection
  document within the example (FR-003); the harness must not hard-code
  assumptions that preclude documenting those choices.
- The confidential tier runs under the confidential runtime class only; this
  example does not integrate attestation or Trustee secret retrieval.
  Attested secret delivery is demonstrated by other repository examples
  (for example kbs-client and block-storage-encrypted) and is out of scope
  here.
- AI/ML training or inference benchmarks are explicitly out of scope for this
  feature; the extensibility requirement (FR-012) exists because a
  physics-relevant (non-AI) benchmark is the anticipated next addition.
- Full-system means all GPUs on a single node; multi-node benchmarks are out
  of scope.
- Results land in a Markdown report plus self-describing local tables on the
  control machine, following the io-benchmark result conventions; no metrics
  or results leave the cluster/control machine.
- The workload image with GPU benchmark binaries follows the externally built,
  pinned-and-overridable pattern used by `perf-utils` in io-benchmark; this
  repository takes no supply-chain ownership of it.
- The feature measures and reports the confidential-vs-standard delta; it does
  not promise any specific delta value, which is an outcome of measurement
  rather than a deliverable.
