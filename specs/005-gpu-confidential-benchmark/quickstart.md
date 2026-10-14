# Quickstart: GPU Confidential Benchmark Validation

**Feature**: 005-gpu-confidential-benchmark | **Date**: 2026-10-14

Runnable validation scenarios proving the feature end-to-end. Prerequisites,
commands, and expected outcomes only — implementation details live in
`tasks.md` and the implementation. CLI surface: [contracts/operator-surface.md](contracts/operator-surface.md);
entities: [data-model.md](data-model.md).

## Prerequisites

| Need | Why | Notes |
|------|-----|-------|
| `oc` cluster login, permission to create Pod/ConfigMap in the namespace | all case operations | |
| `helm` v3 | chart rendering | |
| Python 3.12 on control machine | approved tool | `pip install ./gpu-benchmark/tools` (pyproject pins pyiceberg, pyarrow, typer; installs `gpu-bench`) |
| Bare-metal OpenShift node with NVIDIA **H100-or-newer** GPUs | FR-002 gate | Older GPUs — including other NVIDIA models — are rejected at preflight |
| NFD + NVIDIA GPU Operator (with CC manager) + OpenShift sandboxed containers operator | confidential GPU path (research R2) | Provides `kata-cc-nvidia-gpu` runtime class and GFD node labels |
| Nominated **isolated** node | FR-009 | Harness census-warns only; isolation is the engineer's responsibility |
| Airgapped environments | FR-017 | Override the workload image with a full immutable reference; no startup downloads |

## Scenario 1 — Preflight only (nothing provisioned)

```sh
gpu-bench --dry-run --node worker-gpu1 --run-tag qs-preflight
```

**Expected**: `PREFLIGHT` lines listing GPU model (passes H100-or-newer
allowlist), GPU count, NVLink presence, runtime classes, detected GPU
resource, image reference; exit `0`. On an ineligible node: actionable
prerequisite message and exit `1` **before anything is provisioned**.

## Scenario 2 — Single-GPU confidential-vs-standard comparison (US1, SC-001)

```sh
gpu-bench --node worker-gpu1 --gpu-config single \
  --tiers plain,coco --benchmarks hpl,hpl-mxp \
  --run-tag qs-single --yes
```

**Expected**:
- `PREFLIGHT OK` then `CASE <slug> DONE` for each of the four cases
  (hpl/hpl-mxp × plain/coco), strictly serially — never two pods at once.
- `results/qs-single/summary.md` shows per-case Gflops with verification
  status and a **delta table**: confidential vs standard per benchmark,
  computed only from verified iterations (SC-003).
- Raw HPL/HPL-MxP output (with residual-check verdict) and in-pod
  `nvidia-smi` device evidence under `results/qs-single/<case>/`.
- Iceberg rows appended to `results/iceberg-warehouse/`.
- Exit `0`; no leftover pods/configmaps on the cluster.

## Scenario 3 — Full-system multi-GPU comparison (US2, SC-002)

On a 4- or 8-GPU NVLink node:

```sh
gpu-bench --node worker-gpu8 --gpu-config full \
  --tiers plain,coco --benchmarks hpl \
  --run-tag qs-full --yes
```

**Expected**: all node GPUs used in one benchmark process set per case;
verified multi-GPU Gflops and the confidential-vs-standard delta in
`summary.md`; identical `N/NB/P/Q` across tiers (FR-004).

**Negative check**: request `--gpu-config full` on a node without NVLink —
preflight must reject with the topology requirement (exit `1`, nothing
provisioned). Request it with a GPU-count expectation above the node's
actual count — the harness surfaces the actual count and never reports a
partial run as full-system.

## Scenario 4 — Verification gating (US1 scenario 4, SC-003)

Force a failing residual check (e.g., override problem parameters to a
degenerate value via `--hpl-n`).

**Expected**: the iteration is marked **invalid**, excluded from the delta
table (shown as a status gap, never as a number), exit `2`; verified runs
from the same invocation still report normally.

## Scenario 5 — Catalog extensibility (US3, SC-004)

```sh
# Add a placeholder definition to gpu-benchmark/benchmarks/ (data file only):
#   id: placeholder, precision: fp64, parser with metric+verification, ...
gpu-bench --dry-run --node worker-gpu1 --benchmarks placeholder
```

**Expected**: the placeholder is discovered and selectable with **zero**
changes to existing definitions, the chart (`helm lint --strict` still
passes untouched), or the reporting flow. Remove the placeholder afterwards.

## Scenario 6 — Interruption recovery

```sh
# Ctrl-C mid-run, or control machine dies, then:
gpu-bench --cleanup-only qs-single
```

**Expected**: deterministic deletion of the run's pod/configmap by label
`gpu-benchmark/run-tag=qs-single`, deletion verified; exit `0` (clean) or
`4` (resources remain — re-run).

## Reproduction criterion (SC-005)

A platform engineer with only `gpu-benchmark/README.md` can repeat Scenario 2
on a second suitably provisioned cluster and obtain the same artifact set and
report shape. CI (lint-level) passes: `helm lint --strict`, values schema
validation, `python3 -m py_compile`, `shellcheck tests/run.sh` (SC-006).
