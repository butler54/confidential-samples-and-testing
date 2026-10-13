# Feature Specification: IO Benchmark Harness for Confidential Pods

**Feature Branch**: `004-benchmark-harness`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Provide a mechanism for testing IO performance of a single pod in a stable repeatable way, well characterized. Objective: a script to run end-to-end tests. Thorough analysis of available benchmarks (fio assumed; sysbench alternative; dbench considered/wrapped/forked) before writing code. Earlier iteration (staging/fio-script) focused on vertical CPU/memory scaling with unclear importance. Results must be parsed into a summary table. Compare six cases: plain pod, plain pod with the same encrypted storage as coco, kata pod, kata pod with encrypted storage, coco pod, coco pod with encrypted storage. Runs on a nominated node, serially, with a nominated raw-block-capable storage class, for a configurable container size. Benchmark workload covers a broad spectrum (block sizes 4k–1M); volume size configurable and large enough for enterprise SAN controllers / nodes with 200GB+ memory; best practices so we measure disk IO, not buffers. Constraints: airgap-deployable (image overrides), OpenShift."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Documented, defensible benchmark tool selection (Priority: P1)

A performance-testing stakeholder needs the benchmark tool choice to be a deliberate, analyzed decision — not inertia from the earlier iteration. Before any harness code exists, a written analysis evaluates the credible IO benchmark candidates (at minimum fio, sysbench, and dbench — dbench considered as-is, wrapped, or forked) against the feature's needs (raw-block device coverage, configurable block-size spectrum, host-cache-defeating modes, scriptability and machine-parseable output, airgapped availability, operating-system footprint) and records the selection and its rationale.

**Why this priority**: The harness will be quoted in credibility-sensitive confidential-computing comparisons; an unmotivated tool choice undermines every number it produces. The requirement to analyze before coding is explicit in the goal.

**Independent Test**: The analysis document exists in the feature deliverables, covers all three named tools plus any serious alternatives the analysis raises, evaluates them against the stated criteria, selects one primary tool, and states clearly what would change the decision. A reviewer can follow it without prior context.

**Acceptance Scenarios**:

1. **Given** no harness implementation yet, **When** the analysis deliverable is produced, **Then** it names the selected tool, rejects or defers each alternative with a reasoned rationale, and lists the criteria used.
2. **Given** the analysis selects a tool other than the initially assumed one, **When** the harness is subsequently written, **Then** the recorded criteria drive the workload and parameter defaults of that harness.

---

### User Story 2 - One-command, end-to-end single-case benchmark (Priority: P1)

A platform engineer points the harness at a specific node with a chosen storage class, container CPU/memory, and benchmark volume size; a single command provisions the block volume and benchmark pod on that node, applies the storage treatment (plain or encrypted volume), executes the benchmark's full parameter sweep, parses the output into a summary line/table for that case, and removes every provisioned resource.

**Why this priority**: This is the smallest independently valuable slice and the foundation every comparison builds on; without a correct single-case pipeline, a six-case matrix is meaningless.

**Independent Test**: Run the harness once with a single case selected (e.g. plain pod, unencrypted) against a cluster; it requires no cluster state from a previous run, completes without manual intervention, prints the case's parsed summary, and leaves no pod, claim, or backing storage behind.

**Acceptance Scenarios**:

1. **Given** a valid node, storage class, and size input, **When** the single-case run executes, **Then** volume provisioning, pod scheduling onto the nominated node, storage preparation, benchmark execution, result parsing, and cleanup happen in order with no manual steps.
2. **Given** the benchmark pod fails or exceeds its execution limit, **When** the run encounters that failure, **Then** the case is marked failed in the summary, all resources for that case are removed, and the operator sees an actionable message.

---

### User Story 3 - Serial six-case comparison with summary table (Priority: P2)

The engineer runs the full comparison: all six workload cases — plain pod, plain pod with the same encrypted-storage treatment as the confidential pod, sandboxed-VM pod, sandboxed-VM pod encrypted, confidential pod, confidential pod encrypted — executed strictly serially (never overlapping) on one nominated node with one nominated storage class and one container size, then rendered as a single comparison summary table with each case's benchmark metrics and explicit failure markers.

**Why this priority**: The six-case comparison is the stated goal of the feature, but it delivers no value until single-case execution is reliable; it deserves implementation immediately after.

**Independent Test**: Invoke the harness in its default (all-cases) mode; it performs exactly one benchmark pod at a time, and at completion outputs one table with six rows — six cases, one row each, each populated or explicitly marked failed — plus a per-case detailed log location.

**Acceptance Scenarios**:

1. **Given** the full mode invoked with node, storage class, and container size inputs, **When** it runs, **Then** exactly one benchmark pod exists at any moment, and a comparison table of all six cases is emitted at the end.
2. **Given** one case fails mid-run, **When** the run continues, **Then** the remaining cases still execute and the failed case appears as a failure row in the final table.
3. **Given** an operator selects a subset of cases, **When** the invocation filters cases by name or category, **Then** only those cases run, in the documented order.

---

### User Story 4 - Characterized repeatability and honest disk measurement (Priority: P2)

A reader of the results must trust that the numbers measure storage, not buffers: the harness applies and documents the benchmark practices that defeat host-node page cache, pod page cache, and controller cache (direct unsynchronized IO, volume sizing beyond the node's memory, a documented volume-size sizing rule, no inadvertent "tmpfs" or memory-backed paths), and the deliverable reports measured run-to-run variance so operators can tell signal from noise.

**Why this priority**: Without cache-defeating and characterization the comparison numbers can be off by orders of magnitude — silent wrongness on the metric that matters most. It comes after the matrix exists because it relies on real run data.

**Independent Test**: Run a configuration once; the emitted summary quantifies per-benchmark variance across the built-in repeats, and the volume/workload sizing rule is verifiably consistent with the target node's memory (e.g. sizing violations appear as a loud start warning plus a cache-suspect stamp carried on every emitted summary).

**Acceptance Scenarios**:

1. **Given** a node with large memory (e.g. 200GB+), **When** the run is configured with a too-small volume, **Then** the run emits the loud sizing warning, stamps every summary cache-suspect, and proceeds unless the operator aborts — the violation is impossible to miss downstream, never a silent pass.
2. **Given** a completed invocation with the default repeat count, **When** results are summarized, **Then** the summary states observed per-benchmark variance (spread across repeats), demonstrating stability or flagging instability within that single run.
3. **Given** default parameters, **When** benchmark jobs execute, **Then** job settings unsuitable for block-device measurement (buffered-only I'd vector, sub-second duration, memory-truncated working set) are absent by construction of the defaults.

---

### Edge Cases

- The nominated node does not exist, is unschedulable, or lacks the required sandbox/confidential runtime; the run must detect this before provisioning and report the specific check that failed.
- The nominated storage class cannot supply raw-block claim volumes (e.g. only filesystem mode); the run must preflight-validate this rather than hanging at pod startup.
- Node memory exceeds the configured benchmark volume, or the chunk of storage is small enough to sit entirely in caches; the sizing rule makes this a loud, summary-stamped warning, not a hidden pass.
- Provisioning a very large benchmark volume takes longer than generic provisioning timeouts; waits scale with volume size instead of using fixed short timeouts.
- An encrypted-storage case loses its crypt volume mid-benchmark; the case records as failed and remaining cases proceed.
- The user's already-large volume fills up or the benchmark's working set exceeds the provisioned volume; preflight checks working-set fits.
- YAML/image registries are unreachable (airgapped) or mirrored; the run uses operator-provided image references with no attempted pulls to public registries.
- The operator interrupts a run (or the control machine dies); resuming means re-running cases, and the operator is told how to remove any remnants deterministically.
- Another tenant workload is co-scheduled on the nominated node mid-run (quota/preemption notwithstanding): results for affected datapoints remain attributable via the preflight tenant census plus spread reporting, and the summary carries the census warning.
- Two operator invocations target the same local Iceberg folder concurrently; writes must be run-scoped appends under unique run identity so concurrent runs cannot corrupt the shared store.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The deliverable MUST provide a single command-line, end-to-end benchmark execution whose lifecycle per case is: preflight validation → volume provisioning → benchmark pod on the nominated node → storage preparation → benchmark parameter sweep → result parsing → summary emission → complete resource deletion; any step failing must not abort remaining cases (the case is marked failed and the run continues), and deletion must be attempted for anything provisioned even on failure or interruption.
- **FR-002**: The harness MUST define exactly six named workload cases — plain containerized workload, plain with encrypted volume, sandboxed-VM workload, sandboxed-VM with encrypted volume, confidential-VM workload, confidential-VM with encrypted volume — where "encrypted volume" applies the same guest-side full-volume encryption treatment as the repository's existing confidential encrypted-storage example, and the confidential cases use the cluster's confidential VM runtime.
- **FR-003**: All per-run inputs MUST be operator-configurable: target node (research-grade consistency requires one node per run set), provision-capable storage class, container CPU and memory allocation, benchmark volume size (independent of container size), benchmark job/parameter set, cluster namespace/identity, the benchmark tooling container image reference (required for airgapped use), and case selection/filtering. Volume size MUST be configurable separately from the type-tokenized defaults.
- **FR-004**: Execution MUST be strictly serial: at most one benchmark pod exists on the cluster at any time, and case ordering is fixed and documented.
- **FR-005**: Volume sizing MUST be user-configurable and governed by a documented cache-defeating sizing rule: the benchmark volume MUST be at least the target node's total memory plus a documented margin (capturing host page cache, pod page cache, and enterprise storage-controller cache concerns — e.g. the 200GB+ memory nodes this feature anticipates), and preflight MUST evaluate the rule on every run: on violation it emits a loud, explicit warning (reporting the node's detected memory and the rule's required minimum), the run proceeds, and every summary output (human-readable and machine-consumable) is stamped cache-suspect so the numbers can never be cited without the caveat.
- **FR-006**: The benchmark parameter sweep MUST cover a broad, characterized spectrum: block sizes spanning at least 4k through 1M, sequential and random access patterns, read and write (and mixed) directions, and durations long enough to reach steady state — with each datapoint repeated N times per invocation (configurable repeat count, default 3) for variance measurement; sweep contents and repeat count MUST be operator-overridable.
- **FR-007**: Defaults MUST enforce cache-defeating measurement: unsynchronized/direct device access for the benchmark working set, a working set within (not trivially smaller than) the provisioned volume, and no memory-backed or overlay-only target paths.
- **FR-008**: Results MUST be parsed into (a) a human-readable Markdown summary table (printed and written to the run folder) containing, per case and per benchmark datapoint: achieved throughput, IO rate, and mean and tail latency, plus an explicit failure entry for any case that did not produce results; and (b) machine-consumable, self-describing results persisted as Apache Iceberg tables under a configurable local folder on the control machine, so results are queryable and cross-run comparable without bespoke parsing; detailed per-case raw logs MUST be retained in the run folder and referenced from the summary.
- **FR-009**: The harness MUST be deployable and runnable in airgapped environments: the benchmark tooling image reference is an operator parameter with a documented default, and no network dependency beyond the cluster's API is required at run time (no in-pod downloads, no public-registry pulls).
- **FR-010**: The harness MUST run on OpenShift without modifying cluster configuration: it works with default pod admission for ordinary pods, selects sandboxed/confidential runtimes only for the cases that need them, validates their presence on the target node during preflight, and requests minimum-privilege security contexts otherwise (escalation, where unavoidable e.g. for volume encryption tooling, documented).
- **FR-011**: The deliverable MUST include the benchmark-tool selection analysis (per US1) covering at minimum fio, sysbench, and dbench (including "wrap or fork" permutations for dbench), scored against explicit criteria, with the outcome binding on the implementation. Tool adoption scope: exactly ONE tool is selected by the analysis and used end-to-end by the harness; the analysis document remains the rationale record and states what would change the decision.
- **FR-012**: The deliverable MUST document volume-sizing, duration, and expected-variance guidance so a reader can characterize stability (US4), including how to interpret the summary's variance on runs of large-memory nodes and enterprise storage.
- **FR-013**: The harness MUST clean up all created resources on success, failure, and interruption, and MUST document how an operator removes remnants if the control process itself dies; it must not delete pre-existing operator resources by name collision (created resources carry run-scoped names).
- **FR-014**: Container CPU/memory size MUST be a per-run configuration input with a documented default; a single run uses a single size for all its cases, and comparing sizes is done by re-invoking the harness — an in-invocation size sweep (as in the earlier staging iteration) is out of scope.
- **FR-015**: Each benchmark datapoint MUST be executed a configurable number of times per invocation (default 3), and the summary and Iceberg tables MUST report per-datapoint spread (min, max, and standard deviation or relative range) alongside the central value, so variance from a single run is visible without external tooling.
- **FR-016**: The harness MUST NOT mutate node schedulability (no cordon/uncordon, tainting, draining, or eviction). Preflight MUST enumerate the nominated node's co-resident pods and emit a loud, explicit warning whenever unexpected workloads are present (tolerable system/daemonset pods are expected background), so noise-prone results are visibly attributable; the run documentation MUST describe the operator isolation prerequisite (a dedicated node or one drained of cluster workloads other than system daemons).
- **FR-017**: The deliverable MUST NOT define or build any container image. Benchmark workloads in-cluster consume a single externally-built tooling image (documented default `quay.io/rh-ee-chbutler/perf-utils`, built from the `butler54/containers` repository and including fio), referenced through the operator-overridable image input of FR-003; no dedicated fio or summarizer image is created or required by this feature.
- **FR-018**: The control-side benchmark workflow (serial case orchestration, per-repeat in-pod benchmark invocation, raw log collection, result parsing/normalization, Markdown summary emission, and Iceberg appends) MUST be driven by a local tool running on the operator's control machine, implemented as the explicitly-approved Python tool recorded in Clarifications, with pinned and documented dependencies.

### Key Entities

- **Benchmark case**: One of six named workload configurations (workload runtime category × storage treatment), i.e., the thing being compared; attributes: name, runtime requirement (ordinary/sandboxed/confidential), storage treatment (plain block, encrypted volume).
- **Run configuration**: Operator inputs for one invocation: nominated node, storage class, container CPU/memory, benchmark volume size, benchmark sweep parameters, image references, case filter; must be self-contained so a run is reproducible later.
- **Benchmark datapoint**: One sweep entry inside a case (e.g. random read at 4k): its block size, pattern, direction, duration, and measured throughput / IO rate / latency statistics.
- **Case result**: Aggregated outcome of one case: its datapoints, failure state if any, and reference to raw logs.
- **Comparison summary**: The per-run table mapping the six (or filtered subset of) cases to their case results, plus run-configuration metadata needed to interpret the numbers (node, storage class, container size, volume size, tool version, timestamps).
- **Local Iceberg result store**: A self-describing Apache Iceberg dataset on the control machine's local filesystem (per-run table appends identified by run identity), holding the machine-consumable form of every case result and datapoint; it is the cross-run comparison medium and is itself excluded from the intentional deletion lifecycle of cluster resources.
- **Sizing rule**: The documented relationship between benchmark volume size, node memory, pod memory, and known caching layers that determines whether the run is measurably honest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator with valid permissions can take a documented input set (node, storage class, size, volume size) and obtain the complete six-case comparison table in one invocation, with zero manual intervening steps after initiation and zero resources left behind on the cluster (verified by inspection).
- **SC-002**: 100% of attempted cases appear in the summary output — as measured rows or explicitly-marked failure rows — and a mid-run failure of any single case never prevents the remaining cases from starting.
- **SC-003**: A single invocation emits, for every benchmark datapoint, central value plus measured spread across the invocation's repeats (min, max, and standard deviation or relative range), and the deliverable documents guidance for interpreting spreads; per-benchmark relative spread on a stable cluster is reported as measured data so readers can judge stability thresholds for their platform.
- **SC-004**: Every benchmark datapoint in the summary is produced with unsynchronized direct IO against a raw block device sized per the documented cache-defeating sizing rule (FR-005), so concluded numbers cannot be explained by pure caching *unless* deliberately run under a sizing violation — in which case every emitted summary is visibly stamped cache-suspect — verified by preflight evaluation and inspection of the applied job settings.
- **SC-005**: The full workflow runs to completion in an environment with no public-registry and no external-network access, using only image references supplied through the airgap override input, with no documented manual mirroring step omitted from the delivered instructions.
- **SC-006**: The analysis deliverable covers fio, sysbench and dbench (including at least the "wrapped" and "forked" evaluations of dbench), names a clear primary selection, and would allow a knowledgeable reader to replicate the decision given the same criteria — reviewable without the implementer present.

## Clarifications

Progressively resolved; sessions record answers and the affected requirement text.

### Session 2026-10-13

- Q: How many benchmark tools must the harness carry after the fio/sysbench/dbench analysis? → A: Exactly one — the analysis selects a single tool used end-to-end; the analysis document is the binding rationale record (FR-011).
- Q: Container CPU/memory sizing behavior across runs? → A: Single configurable size per run; re-invoke to compare sizes; in-invocation size sweep out of scope (FR-014).
- Q: Cache-defeating volume sizing rule? → A: Volume ≥ node total RAM + documented margin, enforced at preflight with the detected node memory and required minimum reported to the operator (FR-005).
- Q: Should benchmark variance be measured by built-in repeats within one invocation, or by comparing separate invocations? → A: Built-in repeats — each benchmark datapoint runs N times per invocation (configurable, default 3) and the summary reports spread (min/max/stddev or relative range) beside each mean, so SC-003 is verifiable within a single run.
- Q: What should the harness do about non-benchmark workloads co-resident on the nominated node? → A: Node isolation is the operator's responsibility (documented prerequisite: dedicated or effectively emptied node); the harness preflight-reports the node's tenant census and warns loudly on unexpected co-resident workloads, and MUST never cordon, taint, evict, or otherwise mutate node schedulability.
- Q: Should the FR-005 sizing rule be a hard failure with an explicit acknowledgment override, a hard failure with no override, or a non-blocking warning? → A: Non-blocking — preflight evaluates the rule and emits a loud, explicit warning; the run proceeds, and every emitted summary output is stamped cache-suspect so numbers can never be cited without the caveat.
- Q: Which formats should the summary table be emitted in? → A: Markdown table for humans plus a machine-consumable form (initially JSON) (FR-008).
- Q: Should result data persist in a self-describing dataset format, and where? → A: Yes — Apache Iceberg tables under a configurable local folder on the control machine; this supersedes JSON as the machine-consumable form while the Markdown table remains the human-readable summary (FR-008).

### Session 2026-10-13 (post-constitution-v2.0.0 update)

- Q: Which container image provides the benchmark tooling inside pods? → A: The existing `quay.io/rh-ee-chbutler/perf-utils` image — built externally (outside this repository, per constitution v2.0.0 IV) from the `butler54/containers` repository's `standard-quay/perf-utils` Containerfile; it is UBI9-based and includes fio 3.x. This feature defines and builds NO container images; the tooling image reference is a documented default consumed as an override-capable operator input (FR-003, FR-009). No dedicated fio image is required or created (FR-017).
- Q: Is scripting beyond shell permitted for the control-side workflow? → A: Yes — because of the workflow's complexity (serial per-case lifecycle management, per-repeat in-pod benchmark invocations, raw log collection, result parsing/normalization, Markdown emission, and Iceberg appends), a local Python tool running on the operator's control machine is EXPLICITLY APPROVED (recorded here as the explicit-advance-approval required by constitution v2.0.0 II). Dependencies are pinned; repository CI validates the tool per the repository lint pipeline (FR-018).
- Q: Is a separate result-parsing/summarization container image (e.g. a "fio-summarizer") required? → A: No — result parsing, normalization, Markdown summary generation, and Iceberg appends are handled by the approved local Python tool; this feature neither builds nor defines any such image (FR-017).

## Assumptions

- "Coco pod" / confidential workload means the cluster's confidential VM runtime class (kata-cc with TDX) as used by the coco-pattern; "kata" means the sandboxed VM runtime class; presence of these runtimes on the nominated node is a cluster prerequisite validated at preflight, not installed by this feature.
- Isolated benchmarking environment: the operator supplies the nominated node in a dedicated or effectively-drained state (only system daemons remain); the harness reports but never enforces this isolation.
- Encryption is the guest-side full-volume LUKS treatment already demonstrated by this repository's encrypted-storage example; because steady-state benchmark IO occurs after unlock, attestation/key-delivery ceremony is out of scope — a clearly-labelled demonstration-grade static key unlock is acceptable and documented as such (attested key remainings an operator option).
- Results are retained on the operator's control machine (summary table + per-case raw logs in a run folder, and the self-describing local Iceberg result store in a configurable local folder); no persistent in-cluster result store is required.
- The harness is delivered consistent with repository conventions (self-contained example directory, charts where genuine resources must be expressed, no in-repo container image definitions — per FR-017 the benchmark tooling image is the existing externally-built `quay.io/rh-ee-chbutler/perf-utils` image, referenced by an override-capable value; control-side orchestration is the explicitly-approved local Python tool per FR-018).
- A single raw-block claim volume per benchmark pod is the storage unit; parallel devices are considered sweeps out of scope.
- Benchmarks run against a provisioned block device (filesystem treatment lives on top of the device inside the case, mirroring the established example) — bench-to-frozen-PVC is not a target use case.
- The earlier staging iteration informs requirements and pitfalls (e.g. hostpath storage classes not supporting raw block, fixed passwords, sidecar mount handoff fragility) but its code is explicitly not a baseline for reuse; where its results logs suggest vertical CPU/memory sensitivity, that is handled by FR-014's clarification.

## Out of Scope

- Multi-pod, multi-node, or concurrent-node benchmark orchestration (noise-oriented, explicitly avoided; serial by design).
- Network, CPU, or memory benchmarking — this feature is storage IO only.
- Attestation-driven key delivery pipelines and Trustee integration for the benchmark volumes (steady-state measurement doesn't depend on key-delivery ceremony; documented option only).
- Automated regression gating in CI on benchmark numbers; validation for this feature remains the repository's lint/shell pipeline plus documented manual verification.
- Long-running result baselining/trend databases; the local Iceberg result store and run folders are the comparison medium.
