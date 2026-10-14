# Data Model: GPU Confidential Benchmark (Phase 1)

**Feature**: 005-gpu-confidential-benchmark | **Date**: 2026-10-14

Entities follow the io-benchmark result conventions (research R5) extended
with the GPU benchmark catalog and comparison dimensions. All entities are
control-machine artifacts (local files and Iceberg tables); nothing is
persisted in-cluster beyond the transient benchmark Pod.

---

## Benchmark

A declarative catalog entry (YAML in `gpu-benchmark/benchmarks/`); the
extensibility unit (FR-012, SC-004).

| Field | Type | Description / Validation |
|---|---|---|
| `id` | string | Unique catalog key (first entries: `hpl`, `hpl-mxp`) |
| `precision` | enum | `fp64` or `mixed` — metrics compared only within the same benchmark, never across precisions (R8) |
| `version` | string | Benchmark binary version, recorded from the pinned image (e.g., HPL 26.02.01) |
| `parameter_inputs` | object | Declarative inputs the runner uses to generate `HPL.dat` (memory-fill fraction, default `NB`, process-grid rule) — see Benchmark Run |
| `command_template` | string | In-pod command with placeholders for computed parameters |
| `parser` | object | Mapping of metric field (Gflops) and verification field (residual check verdict) from benchmark output |
| `docs_ref` | string | Path to the benchmark's documentation/selection rationale |

Validation: `id` unique across catalog; `parser` must yield exactly one
metric and one verification verdict per execution; unknown ids in operator
selection fail preflight with the available catalog listed.

State transitions: none (static definitions). Lifecycle rule: adding a
definition must not require modifying any existing definition, the chart,
or reporting (SC-004).

## Benchmark Case

The unit of execution and measurement: one benchmark × runtime tier × GPU
configuration.

| Field | Type | Description / Validation |
|---|---|---|
| `slug` | string | Canonical case identity, e.g., `hpl-coco-single`, `hpl-mxp-plain-full` |
| `benchmark_id` | string | FK → Benchmark |
| `tier` | enum | `plain`, `kata` (optional), `coco` |
| `runtime_class_name` | string | `""` (plain), `kata-nvidia-gpu` (kata), `kata-cc-nvidia-gpu` (coco) — existence verified at preflight when selected |
| `gpu_config` | enum | `single` or `full` |
| `gpu_count` | integer | 1 for single; GFD node GPU count for full — never a silent subset (US2 scenario 3) |
| `gpu_resource` | string | `nvidia.com/gpu` or `nvidia.com/pgpu`, preflight-detected (R2) |

Validation: at most one case executing at any time (FR-009); all cases of a
run target the same node; tier set is a subset of
{plain, kata, coco} with plain+coco as the default pair.

State transitions:

```text
queued → running → verified | invalid | env-failed
```

- `verified`: benchmark completed and residual check passed → counts as a
  performance result.
- `invalid`: benchmark completed but residual check failed → excluded from
  comparisons (FR-007).
- `env-failed`: pod/runtime/assignment failure → reported distinctly as an
  environment problem, never as performance (US1 scenario 3).

## Benchmark Run

One serial execution of a selected case set on one nominated node under a
run tag.

| Field | Type | Description / Validation |
|---|---|---|
| `run_id` | string | Run tag; unique per `results/` root; names the run directory |
| `node` | string | The single nominated node (all cases on one node) |
| `gpu_model` | string | From GFD `nvidia.com/gpu.product`; must pass the H100-or-newer allowlist (FR-002) |
| `gpu_count_total` | integer | GFD `nvidia.com/gpu.count` on the node |
| `nvlink_present` | boolean | GFD `nvidia.com/nvlink.present`; required true for `full` cases |
| `selected_benchmarks` | list[string] | FKs → Benchmark |
| `selected_tiers` | list[enum] | Default `plain,coco` |
| `gpu_config` | enum | `single` or `full` for the invocation |
| `operator_inputs` | object | Resolved flags, recorded verbatim in `run.env` (sans secrets) |
| `hpl_params` | object | Computed once per (benchmark, gpu_config): `N`, `NB`, `P`, `Q`, memory-fill — identical across tiers (FR-004) |
| `started_at` / `finished_at` | timestamp | Run envelope |

State transitions:

```text
initialized → preflight → executing → complete
                                  ↘ aborted (preflight-fail | env-fail | cleanup-fail)
```

Validation: preflight failures abort before any workload is provisioned;
`full` requires `nvlink_present == true` and `gpu_count_total` equal to the
declared expectation (proceed-with-confirmation allowed, silent subset
never); GPU-occupancy census is warn-only (FR-009).

## Result Record (Case Iteration)

The outcome of one case execution (one repeat).

| Field | Type | Description / Validation |
|---|---|---|
| `run_id` | string | FK → Benchmark Run |
| `case_slug` | string | FK → Benchmark Case |
| `benchmark_id` / `precision` | string / enum | Denormalized from Benchmark |
| `tier` / `gpu_config` / `gpu_count` | enum / enum / int | Denormalized from case |
| `assigned_devices` | list[string] | Device identities from in-pod `nvidia-smi` (R10) |
| `metric_gflops` | float | > 0; parsed per benchmark parser |
| `verified` | boolean | Residual-check verdict; must be true to count (FR-007) |
| `status` | enum | `verified`, `invalid`, `env-failed` (case state machine) |
| `duration_s` | float | Wall-clock of benchmark execution |
| `hpl_params` | object | The exact parameters used (traceability) |
| `raw_output_path` | string | Path to the case's raw benchmark output under `results/<run-tag>/` |

Validation: a performance number exists in the store only together with its
`verified` status and raw-output path (SC-003 traceability); `env-failed`
iterations carry no metric.

## Case Aggregate

Per (run, case): `min`, `max`, `mean`, `stddev`, `spread` of `metric_gflops`
over verified iterations only — mirroring io-benchmark
`runs.case_aggregates`.

## Comparison Report

Side-by-side confidential-vs-standard presentation per
(benchmark, gpu_config), emitted into `summary.md` and derivable from the
Iceberg tables.

| Field | Type | Description / Validation |
|---|---|---|
| `benchmark_id` | string | Deltas computed within one benchmark only (R8) |
| `gpu_config` / `gpu_count` | enum / int | Same configuration both sides |
| `plain_metric` | float | Aggregate (mean) of verified plain-tier iterations |
| `coco_metric` | float | Aggregate (mean) of verified coco-tier iterations |
| `delta` | float | `(coco - plain) / plain`, reported as percentage |
| `pair_verified` | boolean | True only when both sides have ≥1 verified iteration |

Validation: a delta row is emitted **only** when both sides have verified
iterations; missing or unverified sides are shown as gaps with status, never
as numbers (SC-003). No target delta is promised — the delta is a measured
outcome (spec assumption).

---

## Relationships

```text
Benchmark 1──* Benchmark Case *──1 Benchmark Run
Benchmark Run 1──* Result Record (Case Iteration) 1──1 Case Aggregate
Result Record *──1 Benchmark Case (denormalized tier/gpu dims)
Comparison Report := aggregate join of Result Records on
                     (benchmark_id, gpu_config) across tiers plain ↔ coco
```

## Iceberg surface (mirrors io-benchmark, R5)

```text
results/iceberg-warehouse/
├── runs.metadata          # one row per invocation (node, gpu model, params, census flags)
├── runs.case_iterations   # one row per case execution (Result Records)
├── runs.datapoints        # per (case, repeat) parsed metric + verified status
└── runs.case_aggregates   # per case: min/max/mean/stddev/spread over verified iterations
```
