# Contract: Operator Surface (`gpu-bench`)

**Feature**: 005-gpu-confidential-benchmark | **Date**: 2026-10-14

The control-side runner `gpu-bench` (console script from
`gpu-benchmark/tools`, approved per spec FR-015) is the only operator entry
point. Every flag maps one-to-one to run inputs recorded in
`results/<run-tag>/run.env`. Exit codes mirror the io-benchmark contract.

## Invocation

```sh
gpu-bench --node <node> [flags]
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--node` | (required) | Nominated node; all cases of the run execute on it (FR-009) |
| `--benchmarks` | `hpl,hpl-mxp` | Benchmark catalog ids to run; unknown ids fail preflight listing the catalog |
| `--tiers` | `plain,coco` | Runtime tiers; `kata` accepted where the cluster serves `kata-nvidia-gpu` |
| `--gpu-config` | `single` | `single` or `full` (all node GPUs over NVLink; preflight-gated on `nvidia.com/nvlink.present`) |
| `--repeats` | `1` | Serial repeats per case |
| `--run-tag` | (required) | Run identity; names `results/<run-tag>/` |
| `--results-root` | `./results` | Root for run folders and the shared Iceberg warehouse |
| `--workload-image` | pinned default | Full immutable image reference override (mirror/airgap, FR-017) |
| `--gpu-model-allowlist` | built-in H100+ set | Extra CC-capable model names to accept (FR-002 gate stays H100-or-newer semantics) |
| `--hpl-n`, `--hpl-nb`, `--hpl-p`, `--hpl-q` | computed | Parameter overrides; applied identically to every tier (FR-004) |
| `--memory-fill` | `0.8` | Fraction of aggregate GPU memory the problem fills (see docs/sizing-guidance.md) |
| `--dry-run` | off | Preflight only; nothing provisioned |
| `--yes` | off | Non-interactive confirmation of the resolved plan |
| `--cleanup-only <run-tag>` | — | Deterministic recovery: delete by label, verify deletion |

## Preflight gates (fail-fast, before provisioning — FR-010)

1. Node exists; GFD labels present (`nvidia.com/gpu.product`, `gpu.count`,
   `nvlink.present`) — missing labels name NFD/GPU Operator as prerequisite.
2. `gpu.product` passes the H100-or-newer allowlist (FR-002); other models,
   including other NVIDIA models, are rejected.
3. Selected runtime classes exist on the cluster (`kata-cc-nvidia-gpu`,
   `kata-nvidia-gpu` when selected).
4. GPU resource served (`nvidia.com/gpu` or `nvidia.com/pgpu`) and
   allocatable count ≥ requested.
5. `full` config: `nvlink.present == true` and node GPU count matches the
   declared expectation (proceed-with-confirmation allowed; silent subset
   never — US2 scenario 3).
6. Workload image reference resolvable/overridden (airgap path, FR-017).
7. GPU-occupancy census on the node — **warn-only** (FR-009).

## Execution contract (FR-009)

- Cases run strictly serially; at most one benchmark Pod exists at any time.
- One Helm render/apply per case; the exact applied manifest is archived as
  `manifest-<case>.yaml`.
- Benchmark execution via bounded `oc exec`; transcript archived as
  `exec-<case>.log`; pod logs collected before deletion.
- Every case ends with deterministic deletion of its Pod/ConfigMap and
  verification of deletion (label `gpu-benchmark/run-tag=<tag>`).
- The harness never cordons, drains, or evicts anything.

## Results (FR-008; details in data-model.md)

```text
results/<run-tag>/
├── run.env                  # resolved operator inputs (sans secrets)
├── preflight.log            # fixed-format PREFLIGHT lines
├── manifest-<case>.yaml     # exactly what was applied, per case
├── exec-<case>.log          # orchestration transcript per case
├── <case>/rep<N>/           # raw HPL / HPL-MxP output + nvidia-smi evidence
├── LOGS/case-pod-<case>.log # pod logs collected before delete
└── summary.md               # per-case table + confidential-vs-standard delta table

results/iceberg-warehouse/   # shared across runs
├── runs.metadata, runs.case_iterations, runs.datapoints, runs.case_aggregates
```

Verified-only rule: performance numbers appear only for iterations whose
residual check passed; gaps are shown with status, never as numbers
(FR-007/SC-003).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Run complete; all cases verified |
| `1` | Preflight failure (actionable message; nothing provisioned) |
| `2` | One or more cases invalid or env-failed (details in report) |
| `3` | Usage error or operator abort at the confirmation prompt |
| `4` | Leftover cleanup failed after interruption (`--cleanup-only` re-run advised) |
